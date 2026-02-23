"""MainWindow — full game GUI: board + controls + move log + engine integration."""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTextEdit, QMessageBox, QStatusBar, QLabel, QComboBox,
    QGroupBox, QGridLayout, QFileDialog,
)

from duchess.board import DuchessBoard
from duchess.engine_wrapper import UCIEngine, get_engine
from duchess.attacks import compute_attack_maps
from duchess.gui.board_widget import ChessBoardWidget
from duchess.gui.eval_bar import EvaluationBar
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
        self.resize(900, 650)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._player_color = "white"
        self._move_number = 1
        self._workers = {}          # engine_name -> EngineWorker
        self._engines = []          # list of UCIEngine instances
        self._analysis_rows = {}    # engine_name -> {depth, score, pv} QLabels
        self._heatmap_on = False

        # --- Widgets ---
        self._eval_bar = EvaluationBar()
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

        # Analysis panel
        self._analysis_box = QGroupBox("Analysis")
        self._analysis_layout = QGridLayout()
        self._analysis_layout.setColumnStretch(2, 1)  # PV column stretches
        self._analysis_box.setLayout(self._analysis_layout)
        controls.addWidget(self._analysis_box)

        # Load external engine button
        btn_load = QPushButton("Load External Engine...")
        btn_load.clicked.connect(self._load_external_engine)
        controls.addWidget(btn_load)

        # Threat heatmap toggle
        self._btn_heatmap = QPushButton("Threat Heatmap")
        self._btn_heatmap.setCheckable(True)
        self._btn_heatmap.clicked.connect(self._toggle_heatmap)
        controls.addWidget(self._btn_heatmap)

        # Opening book controls
        book_box = QGroupBox("Opening Book")
        book_layout = QVBoxLayout()
        engine = get_engine()
        book_label_text = engine.book_name or "None"
        self._book_label = QLabel(f"Book: {book_label_text}")
        book_layout.addWidget(self._book_label)
        btn_load_book = QPushButton("Load Book...")
        btn_load_book.clicked.connect(self._load_custom_book)
        book_layout.addWidget(btn_load_book)
        btn_reset_book = QPushButton("Reset to Default (gm2001)")
        btn_reset_book.clicked.connect(self._reset_default_book)
        book_layout.addWidget(btn_reset_book)
        book_box.setLayout(book_layout)
        controls.addWidget(book_box)

        controls.addStretch()

        # Layout: eval bar | board | controls
        main_layout = QHBoxLayout()
        main_layout.addWidget(self._eval_bar)
        main_layout.addWidget(self._board_widget, stretch=1)

        right_panel = QWidget()
        right_panel.setLayout(controls)
        right_panel.setFixedWidth(300)
        main_layout.addWidget(right_panel)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Welcome to Duchess! Start a new game.")

        # Add Duchess row to analysis panel
        self._duchess_name = "Duchess"
        try:
            self._duchess_name = get_engine().name
        except Exception:
            pass
        self._add_analysis_row(self._duchess_name)

    def _selected_time_ms(self):
        idx = self._time_combo.currentIndex()
        return TIME_OPTIONS[idx][1]

    # --- External engine loading ---

    def _load_external_engine(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select UCI Engine Executable", "", "All Files (*)"
        )
        if not path:
            return
        try:
            engine = UCIEngine(engine_path=path)
        except Exception as e:
            QMessageBox.warning(self, "Engine Error", f"Failed to load engine:\n{e}")
            return
        self._engines.append(engine)
        self._add_analysis_row(engine.name)
        self._status.showMessage(f"Loaded engine: {engine.name}")

    def _add_analysis_row(self, name):
        row = self._analysis_layout.rowCount()
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold;")
        depth_label = QLabel("--")
        score_label = QLabel("--")
        pv_label = QLabel("")
        pv_label.setWordWrap(True)
        self._analysis_layout.addWidget(name_label, row, 0)
        self._analysis_layout.addWidget(depth_label, row, 1)
        self._analysis_layout.addWidget(score_label, row, 2)
        self._analysis_layout.addWidget(pv_label, row, 3)
        self._analysis_rows[name] = {
            "depth": depth_label,
            "score": score_label,
            "pv": pv_label,
        }

    # --- Game management ---

    def _new_game(self, color):
        self._player_color = color
        self._move_number = 1
        self._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self._board_widget.setEnabled(True)
        self._log.clear()
        self._eval_bar.set_score(cp=0)
        # Reset analysis rows
        for row in self._analysis_rows.values():
            row["depth"].setText("--")
            row["score"].setText("--")
            row["pv"].setText("")

        if color == "white":
            self._status.showMessage("Your move (White).")
        else:
            self._status.showMessage("Engine is thinking...")
            self._board_widget.setEnabled(False)
            self._start_engine()

        self._refresh_heatmap()

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
        self._refresh_heatmap()
        self._start_engine()

    # --- Engine ---

    def _start_engine(self):
        fen = self._board_widget.board.fen()
        time_ms = self._selected_time_ms()

        # Duchess (default engine, no explicit instance — uses singleton)
        duchess_worker = EngineWorker(fen, time_ms=time_ms)
        duchess_worker.move_found.connect(self._on_engine_move)
        duchess_worker.search_info.connect(self._on_search_info)
        self._workers["__duchess__"] = duchess_worker
        duchess_worker.start()

        # External engines (ambient analysis only)
        for engine in self._engines:
            worker = EngineWorker(fen, time_ms=time_ms, engine=engine)
            worker.move_found.connect(self._on_engine_move)
            worker.search_info.connect(self._on_search_info)
            self._workers[engine.name] = worker
            worker.start()

    def _on_search_info(self, name, info):
        """Handle real-time search info from any engine."""
        # Determine if this is the Duchess engine
        is_duchess = name == "__duchess__" or "duchess" in name.lower()

        # Update eval bar and PV arrows only for Duchess
        if is_duchess:
            fen = self._board_widget.board.fen()
            side_to_move = fen.split()[1] if len(fen.split()) >= 2 else "w"

            if "score_mate" in info:
                mate = info["score_mate"]
                if side_to_move == "b":
                    mate = -mate
                self._eval_bar.set_score(mate=mate, depth=info.get("depth", 0))
            elif "score_cp" in info:
                cp = info["score_cp"]
                if side_to_move == "b":
                    cp = -cp
                self._eval_bar.set_score(cp=cp, depth=info.get("depth", 0))

            pv = info.get("pv", [])
            if pv:
                self._board_widget.draw_pv_arrows(pv[:4])

            depth = info.get("depth", "?")
            nodes = info.get("nodes", 0)
            nps = info.get("nps", 0)
            self._status.showMessage(f"Thinking... depth {depth}  nodes {nodes}  nps {nps}")

        # Update analysis panel row
        if name in self._analysis_rows:
            row = self._analysis_rows[name]
            row["depth"].setText(f"d{info.get('depth', '?')}")
            if "score_mate" in info:
                row["score"].setText(f"M{info['score_mate']}")
            elif "score_cp" in info:
                row["score"].setText(f"{info['score_cp'] / 100:+.2f}")
            pv = info.get("pv", [])
            if pv:
                row["pv"].setText(" ".join(pv[:6]))

    def _on_engine_move(self, uci, name):
        # Only push moves from Duchess — external engines are ambient analysis
        is_duchess = name == "__duchess__" or "duchess" in name.lower()
        if not is_duchess:
            return

        board = self._board_widget.board

        # Get SAN before pushing
        from duchess.chess_types import Move
        move = Move.from_uci(uci)
        san = board.san(move)

        # Push the move and update display
        board.push(move)
        self._board_widget._last_move_from = move.from_sq
        self._board_widget._last_move_to = move.to_sq
        self._board_widget._selected_sq = None
        self._board_widget.clear_arrows()
        self._board_widget._sync_pieces()

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

        self._board_widget.setEnabled(True)
        turn = "White" if board.turn == "white" else "Black"
        self._status.showMessage(f"Your move ({turn}).")
        self._refresh_heatmap()
        self._workers.clear()

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

    # --- Threat Heatmap ---

    def _toggle_heatmap(self):
        self._heatmap_on = self._btn_heatmap.isChecked()
        if self._heatmap_on:
            self._refresh_heatmap()
        else:
            self._board_widget.clear_heatmap()

    def _refresh_heatmap(self):
        if not self._heatmap_on:
            return
        pieces = [self._board_widget.board.piece_at_sq(sq) for sq in range(64)]
        w, b = compute_attack_maps(pieces)
        self._board_widget.set_heatmap(w, b, self._player_color)

    # --- Opening Book ---

    def _load_custom_book(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Opening Book", "",
            "Polyglot Book Files (*.bin);;All Files (*)"
        )
        if path:
            engine = get_engine()
            engine.set_book(path)
            self._book_label.setText(f"Book: {engine.book_name}")
            self._status.showMessage(f"Loaded opening book: {engine.book_name}")

    def _reset_default_book(self):
        engine = get_engine()
        engine.reset_book()
        name = engine.book_name or "None"
        self._book_label.setText(f"Book: {name}")
        self._status.showMessage(f"Reset to default opening book: {name}")
