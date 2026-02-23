import pytest
from PyQt6.QtCore import Qt, QPoint
from unittest.mock import patch
from duchess.gui.main_window import MainWindow
from duchess.gui.worker import EngineWorker

def test_mainwindow_initialization(qtbot):
    """Test MainWindow opens and initializes UI correctly."""
    window = MainWindow()
    qtbot.addWidget(window)
    
    assert window.windowTitle() == "Duchess Chess"
    assert window._status.currentMessage() == "Welcome to Duchess! Start a new game."

def test_new_game_white(qtbot):
    """Test starting a new game as White."""
    window = MainWindow()
    qtbot.addWidget(window)
    
    with patch.object(window._control_panel.explorer, "update_position"):
        window._new_game("white")
    assert window._player_color == "white"
    assert window._board_widget.isEnabled() is True
    assert window._status.currentMessage() == "Your move (White)."
    assert len(window._engine_manager._workers) == 0

def test_engine_worker_signal(qtbot):
    """Test that EngineWorker can parse FEN and return a move via signal."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    worker = EngineWorker(fen, time_ms=200)  # Short time so it's fast

    with qtbot.waitSignal(worker.move_found, timeout=3000) as blocker:
        worker.start()

    uci_move = blocker.args[0]
    engine_name = blocker.args[1]
    assert len(uci_move) >= 4  # UCI move like e2e4
    assert isinstance(engine_name, str)

    # Engine thread cleanup
    worker.wait()

def test_new_game_black(qtbot):
    """Test starting a new game as Black, which should auto-trigger the engine."""
    window = MainWindow()
    qtbot.addWidget(window)
    
    with patch.object(window._control_panel.explorer, "update_position"):
        with qtbot.waitSignal(window._board_widget.board.move_made_internal if hasattr(window._board_widget.board, 'move_made_internal') else window._board_widget.move_made, timeout=3000, raising=False) as blocker:
            window._new_game("black")
            
            assert window._player_color == "black"
            assert window._status.currentMessage() == "Engine is thinking..."
            assert window._board_widget.isEnabled() is False
            assert len(window._engine_manager._workers) > 0

            # Wait for the Duchess worker to emit move_found
            duchess_worker = window._engine_manager._workers.get("__duchess__")
            assert duchess_worker is not None
            qtbot.waitSignal(duchess_worker.move_found, timeout=3000)
            duchess_worker.wait()

    # After engine moves
    assert window._board_widget.isEnabled() is True
    assert "Your move" in window._status.currentMessage()
    assert len(window._engine_manager._workers) == 0
    assert window._board_widget.board.turn == "black" # It's now black's turn
