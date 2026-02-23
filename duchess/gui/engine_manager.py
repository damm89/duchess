"""EngineManager — manages background engine calculation threads."""
from PyQt6.QtCore import QObject, pyqtSignal

from duchess.gui.worker import EngineWorker
from duchess.engine_wrapper import UCIEngine, get_engine


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
        self._engines = []  # list of external UCIEngine instances

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

        # 1. Start Duchess (default engine via singleton)
        duchess_worker = EngineWorker(fen, time_ms=time_ms)
        self._connect_worker(duchess_worker)
        self._workers["__duchess__"] = duchess_worker
        duchess_worker.start()

        # 2. Start all external ambient engines
        for engine in self._engines:
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
