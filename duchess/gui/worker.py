# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""EngineWorker — runs engine search on a background QThread."""
from PyQt6.QtCore import QThread, pyqtSignal

from duchess.engine import ChessEngine
from duchess.engine_wrapper import UCIEngine


class EngineWorker(QThread):
    move_found = pyqtSignal(str, str)       # (uci_move, engine_name)
    search_info = pyqtSignal(str, dict)     # (engine_name, info_dict)

    def __init__(self, fen, time_ms=1000, engine=None, parent=None):
        super().__init__(parent)
        self._fen = fen
        self._time_ms = time_ms
        self._engine = engine  # UCIEngine instance, or None for default
        if not hasattr(EngineWorker, "_active_workers"):
            EngineWorker._active_workers = []
        EngineWorker._active_workers.append(self)

    def run(self):
        try:
            if self._engine is not None:
                self._engine.set_position_fen(self._fen)
                uci = self._engine.go_movetime(self._time_ms, info_cb=self._on_info)
                self.move_found.emit(uci, self._engine.name)
            else:
                # Default Duchess engine via ChessEngine wrapper
                engine = ChessEngine()
                name = "Duchess"
                try:
                    from duchess.engine_wrapper import get_engine
                    name = get_engine().name
                except Exception:
                    pass
                uci = engine.get_best_move_timed(
                    self._fen,
                    time_ms=self._time_ms,
                    info_cb=self._on_info_with_name(name),
                )
                self.move_found.emit(uci, name)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _on_info(self, info):
        try:
            name = self._engine.name if self._engine else "Duchess"
            self.search_info.emit(name, info)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _on_info_with_name(self, name):
        def cb(info):
            try:
                self.search_info.emit(name, info)
            except Exception as e:
                import traceback
                traceback.print_exc()
        return cb
