# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""DatabaseExplorerWidget — search and filter historical master games."""
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QComboBox, QMessageBox, QCheckBox
)

from duchess.database import SessionLocal
from duchess.models import MasterGame
from duchess.pgn_importer import parse_and_import


class _SearchWorker(QThread):
    """Background thread to execute DB queries without freezing the GUI."""
    finished = pyqtSignal(list, str)  # emits (results_list, error_msg)

    def __init__(self, filters: dict, max_results=1000, parent=None):
        super().__init__(parent)
        self.filters = filters
        self.max_results = max_results

    def run(self):
        db = SessionLocal()
        error_msg = ""
        results = []
        try:
            query = db.query(MasterGame)

            if white := self.filters.get("white"):
                query = query.filter(MasterGame.white.ilike(f"%{white}%"))
            if black := self.filters.get("black"):
                query = query.filter(MasterGame.black.ilike(f"%{black}%"))
            if eco := self.filters.get("eco"):
                query = query.filter(MasterGame.eco.ilike(f"{eco}%"))
            if result := self.filters.get("result"):
                if result != "Any":
                    query = query.filter(MasterGame.result == result)

            # Order by likely highest profile games (highest combined ELO)
            # Falling back to ID as default order
            query = query.order_by(MasterGame.id.desc()).limit(self.max_results)
            
            # Fetch minimal data to populate table quickly
            for game in query:
                results.append({
                    "id": game.id,
                    "white": game.white,
                    "white_elo": game.white_elo or "",
                    "black": game.black,
                    "black_elo": game.black_elo or "",
                    "result": game.result,
                    "eco": game.eco,
                    "date": game.date,
                    "event": game.event,
                    "move_text": game.move_text,
                    "training_use": game.training_use,
                })
        except Exception as e:
            error_msg = str(e)
        finally:
            db.close()
            
        self.finished.emit(results, error_msg)


class _ImportWorker(QThread):
    """Background thread to import a PGN file without freezing the GUI."""
    finished = pyqtSignal(bool, str)  # emits (success, error_msg)

    def __init__(self, pgn_path: str, training_use: bool = False, parent=None):
        super().__init__(parent)
        self.pgn_path = pgn_path
        self.training_use = training_use

    def run(self):
        try:
            parse_and_import(self.pgn_path, training_use=self.training_use)
            self.finished.emit(True, "")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, str(e))


class DatabaseExplorerDialog(QDialog):
    """A dialog to query the local PGN PostgreSQL database.
    
    Emits `game_selected(move_text)` when the user double-clicks a result.
    """
    game_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colossal PGN Database Explorer")
        self.resize(800, 600)
        self._worker = None
        self._results_data = []

        layout = QVBoxLayout(self)

        # 1. Filters Layout
        filters_layout = QHBoxLayout()

        # White Player Filter
        self._white_edit = QLineEdit()
        self._white_edit.setPlaceholderText("White Player...")
        self._white_edit.returnPressed.connect(self._do_search)
        filters_layout.addWidget(QLabel("White:"))
        filters_layout.addWidget(self._white_edit)

        # Black Player Filter
        self._black_edit = QLineEdit()
        self._black_edit.setPlaceholderText("Black Player...")
        self._black_edit.returnPressed.connect(self._do_search)
        filters_layout.addWidget(QLabel("Black:"))
        filters_layout.addWidget(self._black_edit)

        # ECO Filter
        self._eco_edit = QLineEdit()
        self._eco_edit.setPlaceholderText("ECO (e.g. C50)")
        self._eco_edit.setMaximumWidth(80)
        self._eco_edit.returnPressed.connect(self._do_search)
        filters_layout.addWidget(QLabel("ECO:"))
        filters_layout.addWidget(self._eco_edit)

        # Result Filter
        self._result_combo = QComboBox()
        self._result_combo.addItems(["Any", "1-0", "0-1", "1/2-1/2"])
        filters_layout.addWidget(QLabel("Result:"))
        filters_layout.addWidget(self._result_combo)

        # Search Button
        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._do_search)
        filters_layout.addWidget(self._search_btn)

        layout.addLayout(filters_layout)

        # Status and Import Layout
        top_layout = QHBoxLayout()
        self._status_label = QLabel("Enter search criteria and click Search.")
        top_layout.addWidget(self._status_label)
        
        # Spacer
        top_layout.addStretch()
        
        # Import Button
        self._import_btn = QPushButton("Import PGN...")
        self._import_btn.clicked.connect(self._do_import)
        top_layout.addWidget(self._import_btn)
        
        layout.addLayout(top_layout)

        # 2. Results Table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["White", "Black", "Result", "ECO", "Date", "Event", "Training"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # White
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Black
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Result
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # ECO
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Date
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Event
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Training
        
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self._table)

    def _do_search(self):
        """Execute the search query in the background."""
        if self._worker is not None and self._worker.isRunning():
            return  # query already running

        filters = {
            "white": self._white_edit.text().strip(),
            "black": self._black_edit.text().strip(),
            "eco": self._eco_edit.text().strip(),
            "result": self._result_combo.currentText()
        }

        self._search_btn.setEnabled(False)
        self._status_label.setText("Searching...")
        self._table.setRowCount(0)
        self._results_data = []

        self._worker = _SearchWorker(filters, parent=self)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.start()

    def _on_search_finished(self, results, error_msg):
        self._search_btn.setEnabled(True)
        if error_msg:
            QMessageBox.critical(self, "Database Error", error_msg)
            self._status_label.setText("Search failed.")
            return

        self._results_data = results
        self._table.setRowCount(len(results))
        
        for row, g in enumerate(results):
            white_str = f"{g['white']} ({g['white_elo']})" if g["white_elo"] else g["white"]
            black_str = f"{g['black']} ({g['black_elo']})" if g["black_elo"] else g["black"]

            # Set items
            self._table.setItem(row, 0, QTableWidgetItem(white_str))
            self._table.setItem(row, 1, QTableWidgetItem(black_str))
            
            res_item = QTableWidgetItem(g["result"])
            res_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, res_item)
            
            self._table.setItem(row, 3, QTableWidgetItem(g["eco"] or ""))
            self._table.setItem(row, 4, QTableWidgetItem(g["date"] or ""))
            self._table.setItem(row, 5, QTableWidgetItem(g["event"] or ""))

            # Training checkbox
            cb = QCheckBox()
            cb.setChecked(g["training_use"])
            cb.stateChanged.connect(lambda state, game_id=g["id"]: self._toggle_training(game_id, state))
            self._table.setCellWidget(row, 6, cb)

        limit_msg = " (max 1000)" if len(results) == 1000 else ""
        self._status_label.setText(f"Found {len(results)} games{limit_msg}.")

    def _on_row_double_clicked(self, row, col):
        """Emit the move text when a game is selected."""
        if 0 <= row < len(self._results_data):
            game = self._results_data[row]
            self.game_selected.emit(game["move_text"])
            self.accept()  # Close the dialog

    def _toggle_training(self, game_id: int, state: int):
        """Update training_use flag for a single game in the DB."""
        value = state == Qt.CheckState.Checked.value
        db = SessionLocal()
        try:
            game = db.query(MasterGame).get(game_id)
            if game:
                game.training_use = value
                db.commit()
        except Exception as e:
            db.rollback()
            QMessageBox.warning(self, "Error", f"Failed to update training flag: {e}")
        finally:
            db.close()

    # --- PGN Import UI ---
    
    def _do_import(self):
        """Open a file dialog to select a PGN and launch the import worker."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PGN Database", "",
            "PGN Files (*.pgn);;ZStandard Compressed PGNs (*.pgn.zst);;All Files (*)"
        )
        if not path:
            return

        if path.endswith(".zst"):
            QMessageBox.warning(self, "Unsupported Format",
                                "Please extract the .zst file first and import the uncompressed .pgn file.")
            return

        # Ask whether to flag these games for training
        reply = QMessageBox.question(
            self, "Training Data",
            "Include these games for NNUE training?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        training_use = reply == QMessageBox.StandardButton.Yes

        # Disable UI during import
        self._import_btn.setEnabled(False)
        self._search_btn.setEnabled(False)
        self._status_label.setText("Importing massive PGN database... (This may take a minute)")

        self._import_worker = _ImportWorker(path, training_use=training_use, parent=self)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.start()

    def _on_import_finished(self, success: bool, error_msg: str):
        self._import_btn.setEnabled(True)
        self._search_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Import Complete", "PGN database successfully imported!")
            self._status_label.setText("Import successful. Ready to search.")
            self._do_search()  # show new results
        else:
            QMessageBox.critical(self, "Import Failed", f"An error occurred:\n{error_msg}")
            self._status_label.setText("Import failed.")
