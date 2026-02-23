import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from duchess.gui.database_window import DatabaseExplorerDialog, _ImportWorker, _SearchWorker
from duchess.models import MasterGame

# Assuming we have db_session populated or available for test DB


SAMPLE_PGN = """
[Event "FIDE World Cup 2023"]
[Site "Baku AZE"]
[Date "2023.08.24"]
[Round "8.3"]
[White "Carlsen,M"]
[Black "Praggnanandhaa,R"]
[Result "1/2-1/2"]
[WhiteElo "2835"]
[BlackElo "2707"]
[EventDate "2023.07.30"]
[ECO "C47"]

1. e4 e5 2. Nf3 Nc6 3. Nc3 Nf6 4. a3 Bc5 5. Nxe5 O-O 
6. Nxc6 dxc6 7. h3 Re8 8. d3 Bd4 1/2-1/2
"""

def test_database_dialog_init(qtbot):
    dialog = DatabaseExplorerDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Colossal PGN Database Explorer"
    assert dialog._import_btn.text() == "Import PGN..."
    assert dialog._table.rowCount() == 0


def test_import_worker_success(qtbot):
    dialog = DatabaseExplorerDialog()
    qtbot.addWidget(dialog)
    
    with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=("fake.pgn", "")):
        with patch("duchess.gui.database_window.QMessageBox") as mock_box:
            with patch("duchess.gui.database_window.parse_and_import") as mock_parse:
                with patch.object(dialog, "_do_search"):
                    # Trigger the import via the UI
                    dialog._import_btn.click()
    
                    # Let the GUI process the finished slot and update the UI
                    qtbot.waitUntil(lambda: mock_box.information.called, timeout=2000)
                    dialog._import_worker.wait()

                # Verify logic
                mock_parse.assert_called_once_with("fake.pgn", training_use=False)


def test_import_worker_failure(qtbot):
    dialog = DatabaseExplorerDialog()
    qtbot.addWidget(dialog)
    
    with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=("fake.pgn", "")):
        with patch("duchess.gui.database_window.QMessageBox") as mock_box:
            with patch("duchess.gui.database_window.parse_and_import", side_effect=RuntimeError("Test error")):
                dialog._import_btn.click()
                
                # Let the GUI process the finished slot and update the UI
                qtbot.waitUntil(lambda: mock_box.critical.called, timeout=2000)
                dialog._import_worker.wait()


