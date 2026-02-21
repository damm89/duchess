"""MainWindow — full game GUI: board + controls + move log + engine integration."""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTextEdit, QMessageBox, QStatusBar, QLabel, QComboBox,
)

from duchess.board import DuchessBoard
from duchess.gui.board_widget import ChessBoardWidget
from duchess.gui.worker import EngineWorker


def _resource_path(relative: str) -> Path:
    """Resolve asset path for both dev and PyInstaller bundles."""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent.parent / relative


ICON_PATH = _resource_path("assets/duchess_icon.png")

# Thinking time options: (label, milliseconds)
TIME_OPTIONS = [
    ("0.5s", 500),
    ("1s", 1000),
    ("2s", 2000),
    ("5s", 5000),
    ("10s", 10000),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Duchess Chess")
        self.resize(800, 600)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._player_color = "white"
        self._move_number = 1
        self._worker = None

        # --- Widgets ---
        self._board_widget = ChessBoardWidget()
        self._board_widget.move_made.connect(self._on_player_move)

        # Control panel
        btn_white = QPushButton("New Game (White)")
        btn_white.clicked.connect(lambda: self._new_game("white"))
        btn_black = QPushButton("New Game (Black)")
        btn_black.clicked.connect(lambda: self._new_game("black"))
        btn_resign = QPushButton("Resign")
        btn_resign.clicked.connect(self._resign)

        controls = QVBoxLayout()
        controls.addWidget(btn_white)
        controls.addWidget(btn_black)
        controls.addWidget(btn_resign)

        # Thinking time selector
        controls.addWidget(QLabel("Engine time:"))
        self._time_combo = QComboBox()
        for label, _ in TIME_OPTIONS:
            self._time_combo.addItem(label)
        self._time_combo.setCurrentIndex(1)  # default 1s
        controls.addWidget(self._time_combo)

        # Move log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumWidth(200)
        controls.addWidget(QLabel("Moves:"))
        controls.addWidget(self._log)
        controls.addStretch()

        # Layout
        main_layout = QHBoxLayout()
        main_layout.addWidget(self._board_widget, stretch=3)

        right_panel = QWidget()
        right_panel.setLayout(controls)
        main_layout.addWidget(right_panel, stretch=1)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Welcome to Duchess! Start a new game.")

    def _selected_time_ms(self):
        idx = self._time_combo.currentIndex()
        return TIME_OPTIONS[idx][1]

    # --- Game management ---

    def _new_game(self, color):
        self._player_color = color
        self._move_number = 1
        self._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self._board_widget.setEnabled(True)
        self._log.clear()

        if color == "white":
            self._status.showMessage("Your move (White).")
        else:
            self._status.showMessage("Engine is thinking...")
            self._board_widget.setEnabled(False)
            self._start_engine()

    def _resign(self):
        self._board_widget.setEnabled(False)
        self._status.showMessage("You resigned.")
        self._log.append("Resigned.")

    # --- Player move ---

    def _on_player_move(self, uci, san):
        board = self._board_widget.board

        # Log the player's move
        if self._player_color == "white":
            self._log.insertPlainText(f"{self._move_number}. {san} ")
        else:
            self._log.insertPlainText(f"{san}\n")
            self._move_number += 1

        # Check game over after player move
        if board.is_game_over():
            self._handle_game_over()
            return

        # Disable board while engine thinks
        self._board_widget.setEnabled(False)
        self._status.showMessage("Engine is thinking...")
        self._start_engine()

    # --- Engine ---

    def _start_engine(self):
        fen = self._board_widget.board.fen()
        self._worker = EngineWorker(fen, time_ms=self._selected_time_ms())
        self._worker.move_found.connect(self._on_engine_move)
        self._worker.start()

    def _on_engine_move(self, uci):
        board = self._board_widget.board

        # Get SAN before pushing
        from duchess_engine import Move as _CppMove
        move = _CppMove.from_uci(uci)
        san = board.san(move)

        # Push the move and update display
        board.push(move)
        self._board_widget._last_move_from = move.from_sq
        self._board_widget._last_move_to = move.to_sq
        self._board_widget._selected_sq = None
        self._board_widget.update()

        # Log the engine's move
        if self._player_color == "white":
            self._log.insertPlainText(f"{san}\n")
            self._move_number += 1
        else:
            self._log.insertPlainText(f"{self._move_number}. {san} ")

        # Check game over
        if board.is_game_over():
            self._handle_game_over()
            return

        # Re-enable board
        self._board_widget.setEnabled(True)
        turn = "White" if board.turn == "white" else "Black"
        self._status.showMessage(f"Your move ({turn}).")
        self._worker = None

    # --- Game over ---

    def _handle_game_over(self):
        board = self._board_widget.board
        result = board.result()
        self._board_widget.setEnabled(False)

        if result == "1-0":
            msg = "White wins by checkmate!"
        elif result == "0-1":
            msg = "Black wins by checkmate!"
        else:
            msg = "Draw by stalemate!"

        self._status.showMessage(f"Game over — {msg}")
        self._log.append(f"\n{msg} ({result})")
        QMessageBox.information(self, "Game Over", msg)
