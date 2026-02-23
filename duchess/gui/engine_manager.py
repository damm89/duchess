"""EngineManager — manages background engine calculation threads."""
from PyQt6.QtCore import QObject, pyqtSignal

from duchess.gui.worker import EngineWorker
from duchess.gui.worker import EngineWorker
from duchess.engine_wrapper import UCIEngine, get_engine
import os
import shutil
from pathlib import Path


class EngineManager(QObject):
    """
    Centralizes engine thread lifecycles, separating threading concerns from the MainWindow UI.
    Maintains the default Duchess engine plus any loaded external UCIEngines.
    """
    move_found = pyqtSignal(str, str)       # (uci_move, engine_name)
    search_info = pyqtSignal(str, dict)     # (engine_name, info_dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = {}  # engine_name -> EngineWorker
        self._workers = {}  # engine_name -> EngineWorker
        self._engines = []  # list of external UCIEngine instances
        self._syzygy_files = [] # list of paths
        
    def set_syzygy_files(self, files: list[str]):
        """Store custom syzygy files to be symlinked before search."""
        self._syzygy_files = files

    def add_external_engine(self, path: str) -> UCIEngine:
        """Load an external UCI engine from the given path."""
        engine = UCIEngine(engine_path=path)
        self._engines.append(engine)
        return engine

    def external_engines(self) -> list[UCIEngine]:
        """Return the list of loaded external engines."""
        return self._engines

    def start_multipv(self, fen: str, time_ms: int):
        """Start search on the given FEN on all loaded engines, including Duchess."""
        # Clean up any existing running workers before starting new ones
        self.stop_all()
        
        # Prepare Syzygy symlink directory if custom files are selected
        syzygy_dir = None
        if self._syzygy_files:
            syzygy_dir = Path.home() / ".duchess" / "syzygy"
            syzygy_dir.mkdir(parents=True, exist_ok=True)
            
            # Clear old symlinks
            for f in syzygy_dir.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
                    
            # Create new symlinks
            for fpath in self._syzygy_files:
                src = Path(fpath)
                dst = syzygy_dir / src.name
                try:
                    # os.symlink might fail on Windows without admin rights, use hardlink or copy fallback
                    if os.name == 'nt':
                        shutil.copy2(src, dst)
                    else:
                        os.symlink(src, dst)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to link tablebase {src}: {e}")

        # 1. Start Duchess (default engine via singleton)
        engine = get_engine()
        if syzygy_dir:
            engine.set_option("SyzygyPath", str(syzygy_dir))
            
        duchess_worker = EngineWorker(fen, time_ms=time_ms)
        self._connect_worker(duchess_worker)
        self._workers["__duchess__"] = duchess_worker
        duchess_worker.start()

        # 2. Start all external ambient engines
        for engine in self._engines:
            if syzygy_dir:
                try:
                    engine.set_option("SyzygyPath", str(syzygy_dir))
                except Exception:
                    pass
            worker = EngineWorker(fen, time_ms=time_ms, engine=engine)
            self._connect_worker(worker)
            self._workers[engine.name] = worker
            worker.start()

    def _connect_worker(self, worker: EngineWorker):
        worker.move_found.connect(self.move_found.emit)
        worker.search_info.connect(self.search_info.emit)

    def stop_all(self):
        """Cleanly stop and join all running engine workers."""
        for worker in list(self._workers.values()):
            # We don't have a clean "stop" mechanism for UCIEngine searches mid-run
            # so we just let them finish or wait for them in QThread.wait().
            # Depending on how the GUI is implemented, we might just clear references
            # or try to send a stop command to the underlying wrapper.
            # For now, we wait.
            if worker.isRunning():
                worker.wait(3000)
        self._workers.clear()

    def shutdown(self):
        """Called when the application is closing."""
        self.stop_all()
        for engine in self._engines:
            try:
                engine.quit()
            except Exception:
                pass
        self._engines.clear()
