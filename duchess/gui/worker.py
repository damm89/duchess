"""EngineWorker — runs engine search on a background QThread."""
from PyQt6.QtCore import QThread, pyqtSignal

from duchess.engine import ChessEngine


class EngineWorker(QThread):
    move_found = pyqtSignal(str)

    def __init__(self, fen, time_ms=1000, parent=None):
        super().__init__(parent)
        self._fen = fen
        self._time_ms = time_ms

    def run(self):
        engine = ChessEngine()
        uci = engine.get_best_move_timed(self._fen, time_ms=self._time_ms)
        self.move_found.emit(uci)
