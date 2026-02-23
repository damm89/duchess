# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""MainWindow — full game GUI: board + controls + move log + engine integration."""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTextEdit, QMessageBox, QStatusBar, QLabel, QComboBox,
    QGroupBox, QGridLayout, QFileDialog, QInputDialog, QApplication
)

from duchess.board import DuchessBoard
from duchess.engine_wrapper import UCIEngine, get_engine
from duchess.attacks import compute_attack_maps
from duchess.gui.board_widget import ChessBoardWidget
from duchess.gui.eval_bar import EvaluationBar
from duchess.gui.control_panel import ControlPanelWidget
from duchess.gui.database_window import DatabaseExplorerDialog
from duchess.gui.engine_manager import EngineManager


def _resource_path(relative: str) -> Path:
    """Resolve asset path for both dev and PyInstaller bundles."""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent.parent / relative


ICON_PATH = _resource_path("assets/duchess_icon.png")

# Move time options inside control_panel.py


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Duchess Chess")
        self.resize(900, 650)
        self.setMinimumSize(660, 500)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._player_color = "white"
        self._move_number = 1
        self._engine_manager = EngineManager(self)
        self._engine_manager.move_found.connect(self._on_engine_move)
        self._engine_manager.search_info.connect(self._on_search_info)
        self._heatmap_on = False
        # --- Widgets ---
        self._eval_bar = EvaluationBar()
        self._board_widget = ChessBoardWidget()
        self._board_widget.move_made.connect(self._on_player_move)

        engine = get_engine()
        self._control_panel = ControlPanelWidget(engine.book_name)
        
        # Connect signals
        self._control_panel.new_game_requested.connect(self._new_game)
        self._control_panel.resign_requested.connect(self._resign)
        self._control_panel.load_external_engine_requested.connect(self._load_external_engine)
        self._control_panel.heatmap_toggled.connect(self._toggle_heatmap)
        self._control_panel.load_book_requested.connect(self._load_custom_book)
        self._control_panel.reset_book_requested.connect(self._reset_default_book)
        self._control_panel.db_explorer_requested.connect(self._open_db_explorer)
        self._control_panel.explorer_move_clicked.connect(self._on_explorer_move)
        self._control_panel.syzygy_files_selected.connect(self._engine_manager.set_syzygy_files)

        # Layout: eval bar | board | controls
        main_layout = QHBoxLayout()
        main_layout.addWidget(self._eval_bar)
        main_layout.addWidget(self._board_widget, stretch=1)

        self._control_panel.setFixedWidth(300)
        main_layout.addWidget(self._control_panel)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Welcome to Duchess! Start a new game.")
        
        # Menu bar
        self._create_menu_bar()

        # Add Duchess row to analysis panel
        self._duchess_name = "Duchess"
        try:
            self._duchess_name = get_engine().name
        except Exception:
            pass
        self._add_analysis_row(self._duchess_name)

    def _selected_time_ms(self):
        return self._control_panel.selected_time_ms()

    # --- Menus ---
    
    def _create_menu_bar(self):
        menubar = self.menuBar()
        game_menu = menubar.addMenu("&Game")

        import_fen = QAction("Import FEN...", self)
        import_fen.triggered.connect(self._import_fen)
        game_menu.addAction(import_fen)

        export_fen = QAction("Copy FEN to Clipboard", self)
        export_fen.triggered.connect(self._export_fen)
        game_menu.addAction(export_fen)

        game_menu.addSeparator()

        import_pgn = QAction("Import PGN...", self)
        import_pgn.triggered.connect(self._import_pgn)
        game_menu.addAction(import_pgn)

        export_pgn = QAction("Export PGN...", self)
        export_pgn.triggered.connect(self._export_pgn)
        game_menu.addAction(export_pgn)

        # Advanced Menu
        advanced_menu = menubar.addMenu("&Advanced")

        load_engine = QAction("Load External Engine...", self)
        load_engine.triggered.connect(self._load_external_engine)
        advanced_menu.addAction(load_engine)

        toggle_heatmap = QAction("Toggle Threat Heatmap", self)
        toggle_heatmap.triggered.connect(self._control_panel.heatmap_button.click)
        advanced_menu.addAction(toggle_heatmap)

        advanced_menu.addSeparator()

        load_book = QAction("Load Opening Book...", self)
        load_book.triggered.connect(self._load_custom_book)
        advanced_menu.addAction(load_book)

        reset_book = QAction("Reset Book to Default", self)
        reset_book.triggered.connect(self._reset_default_book)
        advanced_menu.addAction(reset_book)

        colossal_db = QAction("Colossal Database Explorer...", self)
        colossal_db.triggered.connect(self._open_db_explorer)
        advanced_menu.addAction(colossal_db)

        advanced_menu.addSeparator()

        syzygy_tb = QAction("Select Syzygy Tablebases...", self)
        syzygy_tb.triggered.connect(self._control_panel._select_syzygy_files)
        advanced_menu.addAction(syzygy_tb)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("About Duchess...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        QMessageBox.about(self, "About Duchess",
            "<h2>Duchess Chess</h2>"
            "<p>A from-scratch chess engine and analytical GUI.</p>"
            "<p><b>Author:</b> Daniel Ammeraal</p>"
            "<p><b>License:</b> MIT</p>"
            "<p><b>Engine:</b> Custom C++ with UCI protocol<br>"
            "Alpha-beta search, NNUE evaluation, Syzygy tablebases,<br>"
            "Lazy SMP, transposition tables, Polyglot opening books</p>"
            "<p><b>GUI:</b> Python / PyQt6</p>"
            "<hr>"
            "<p><small>Third-party: PyQt6, python-chess, SQLAlchemy, PyTorch, "
            "Catch2, Fathom, gm2001 opening book.<br>"
            "Developed with assistance from Claude by Anthropic.</small></p>"
        )

    def _import_fen(self):
        fen, ok = QInputDialog.getText(self, "Import FEN", "Paste FEN string:")
        if ok and fen:
            try:
                self._board_widget.set_fen(fen)
                self._control_panel.clear_log()
                self._move_number = 1
                self._engine_manager.stop_all()
                self._control_panel.explorer.update_position(self._board_widget.board.fen())
                self._refresh_heatmap()
                self._status.showMessage("Imported FEN position.")
            except ValueError:
                QMessageBox.warning(self, "Invalid FEN", "The provided FEN string is invalid.")

    def _export_fen(self):
        fen = self._board_widget.board.fen()
        QApplication.clipboard().setText(fen)
        self._status.showMessage("FEN copied to clipboard.")

    def _import_pgn(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import PGN", "", "PGN Files (*.pgn);;All Files (*)")
        if path:
            import chess.pgn
            try:
                with open(path, "r") as f:
                    game = chess.pgn.read_game(f)
                if not game:
                    raise ValueError("No game found in PGN.")
                
                board = game.board()
                self._board_widget.set_fen(board.fen())
                self._control_panel.clear_log()
                self._move_number = 1
                self._engine_manager.stop_all()

                for move in game.mainline_moves():
                    san = board.san(move)
                    if board.turn == chess.WHITE:
                        self._control_panel.insert_log(f"{self._move_number}. {san} ")
                    else:
                        self._control_panel.insert_log(f"{san}\n")
                        self._move_number += 1
                    board.push(move)
                
                self._board_widget._sync_pieces()
                self._refresh_heatmap()
                self._control_panel.explorer.update_position(board.fen())
                self._status.showMessage(f"Imported game from {path}")
            except Exception as e:
                QMessageBox.warning(self, "Import Error", f"Could not import PGN:\n{e}")

    def _export_pgn(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PGN", "", "PGN Files (*.pgn)")
        if path:
            import chess.pgn
            try:
                game = chess.pgn.Game.from_board(self._board_widget.board)
                game.headers["Event"] = "Duchess Export"
                with open(path, "w") as f:
                    f.write(str(game))
                self._status.showMessage(f"Exported game to {path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Could not export PGN:\n{e}")

    # --- External engine loading ---

    def _load_external_engine(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select UCI Engine Executable", "", "All Files (*)"
        )
        if not path:
            return
        try:
            engine = self._engine_manager.add_external_engine(path)
        except Exception as e:
            QMessageBox.warning(self, "Engine Error", f"Failed to load engine:\n{e}")
            return
        self._add_analysis_row(engine.name)
        self._status.showMessage(f"Loaded engine: {engine.name}")

    def _add_analysis_row(self, name):
        self._control_panel.add_analysis_row(name)

    # --- Game management ---

    def _new_game(self, color):
        self._player_color = color
        self._move_number = 1
        self._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self._board_widget.setEnabled(True)
        self._control_panel.clear_log()
        self._eval_bar.set_score(cp=0)
        self._control_panel.clear_analysis()

        # Refresh opening explorer for starting position
        self._control_panel.explorer.update_position(self._board_widget.board.fen())

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
        self._control_panel.append_log("Resigned.")

    # --- Player move ---

    def _on_player_move(self, uci, san):
        board = self._board_widget.board

        # Log the player's move
        if self._player_color == "white":
            self._control_panel.insert_log(f"{self._move_number}. {san} ")
        else:
            self._control_panel.insert_log(f"{san}\n")
            self._move_number += 1

        # Check game over after player move
        if board.is_game_over():
            self._handle_game_over()
            return

        # Disable board while engine thinks
        self._board_widget.setEnabled(False)
        self._status.showMessage("Engine is thinking...")
        self._refresh_heatmap()
        self._control_panel.explorer.update_position(self._board_widget.board.fen())
        self._start_engine()

    # --- Engine ---

    def _start_engine(self):
        fen = self._board_widget.board.fen()
        time_ms = self._selected_time_ms()
        self._engine_manager.start_multipv(fen, time_ms)

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
        row = self._control_panel.get_analysis_row(name)
        if row:
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
            self._control_panel.insert_log(f"{san}\n")
            self._move_number += 1
        else:
            self._control_panel.insert_log(f"{self._move_number}. {san} ")

        # Check game over
        if board.is_game_over():
            self._handle_game_over()
            return

        self._board_widget.setEnabled(True)
        turn = "White" if board.turn == "white" else "Black"
        self._status.showMessage(f"Your move ({turn}).")
        self._refresh_heatmap()
        self._control_panel.explorer.update_position(board.fen())
        self._engine_manager.stop_all()

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
        self._control_panel.append_log(f"\n{msg} ({result})")
        QMessageBox.information(self, "Game Over", msg)

    # --- Threat Heatmap ---

    def _toggle_heatmap(self):
        self._heatmap_on = self._control_panel.heatmap_button.isChecked()
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
            self._control_panel.set_book_name(engine.book_name)
            self._status.showMessage(f"Loaded opening book: {engine.book_name}")

    def _reset_default_book(self):
        engine = get_engine()
        engine.reset_book()
        name = engine.book_name or "None"
        self._control_panel.set_book_name(name)
        self._status.showMessage(f"Reset to default opening book: {name}")

    # --- Opening Explorer ---

    def _on_explorer_move(self, uci):
        """Handle a move clicked in the Opening Explorer panel."""
        board = self._board_widget.board

        # Verify the move is legal
        from duchess.chess_types import Move
        move = Move.from_uci(uci)
        legal_ucis = [m.to_uci() for m in board.legal_moves]
        if uci not in legal_ucis:
            return

        san = board.san(move)

        # Log the move
        if board.turn == "white":
            self._control_panel.insert_log(f"{self._move_number}. {san} ")
        else:
            self._control_panel.insert_log(f"{san}\n")
            self._move_number += 1

        # Push the move
        board.push(move)
        self._board_widget._last_move_from = move.from_sq
        self._board_widget._last_move_to = move.to_sq
        self._board_widget._selected_sq = None
        self._board_widget.clear_arrows()
        self._board_widget._sync_pieces()

        # Update explorer for new position
        self._control_panel.explorer.update_position(board.fen())
        self._refresh_heatmap()

        if board.is_game_over():
            self._handle_game_over()

    # --- Database Explorer ---

    def _open_db_explorer(self):
        """Open the PostgreSQL Master Database explorer."""
        dialog = DatabaseExplorerDialog(self)
        dialog.game_selected.connect(self._play_pgn)
        dialog.exec()

    def _play_pgn(self, pgn_text: str):
        """Reset the board and replay a raw PGN move text sequence."""
        self._new_game("white")  # reset board and stop engines
        
        board = self._board_widget.board
        tokens = pgn_text.split()
        
        self._control_panel.clear_log()
        
        # We need to temporarily disable validation bounds because SAN parsing needs piece locations
        # and rapid pushing requires the engine to keep up.
        # It's better to just push each move sequentially.
        
        for token in tokens:
            # Skip move numbers (e.g. "1.", "12...") and results
            if "." in token or token in ["1-0", "0-1", "1/2-1/2", "*"]:
                if "." in token:
                    self._control_panel.insert_log(f"{token} ")
                elif token in ["1-0", "0-1", "1/2-1/2", "*"]:
                    self._control_panel.insert_log(f"\nResult: {token}")
                continue
                
            try:
                # Parse SAN token to Move object
                move = board.parse_san(token)
                board.push(move)
                
                # Log the move text format manually since we don't have turn state available here
                self._control_panel.insert_log(f"{token} ")
                if board.turn == "white":
                    self._control_panel.insert_log("\n")
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to parse SAN move %s from DB: %s", token, e)
                break

        self._board_widget._selected_sq = None
        self._board_widget.clear_arrows()
        self._board_widget._sync_pieces()
        self._refresh_heatmap()
        self._control_panel.explorer.update_position(board.fen())
        self._status.showMessage("Loaded master game from database.")

    def closeEvent(self, event):
        """Cleanly shut down engine workers to prevent QThread destroyed while thread is still running crashes."""
        self._engine_manager.shutdown()
        super().closeEvent(event)
