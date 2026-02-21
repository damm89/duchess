import pytest
from PyQt6.QtCore import Qt, QPoint
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
    
    window._new_game("white")
    assert window._player_color == "white"
    assert window._board_widget.isEnabled() is True
    assert window._status.currentMessage() == "Your move (White)."
    assert window._worker is None

def test_engine_worker_signal(qtbot):
    """Test that EngineWorker can parse FEN and return a move via signal."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    worker = EngineWorker(fen, depth=1)  # Depth 1 so it's fast
    
    with qtbot.waitSignal(worker.move_found, timeout=3000) as blocker:
        worker.start()
        
    move = blocker.args[0]
    assert len(move) >= 4  # UCI move like e2e4
    
    # Engine thread cleanup
    worker.wait()

def test_new_game_black(qtbot):
    """Test starting a new game as Black, which should auto-trigger the engine."""
    window = MainWindow()
    qtbot.addWidget(window)
    
    with qtbot.waitSignal(window._board_widget.board.move_made_internal if hasattr(window._board_widget.board, 'move_made_internal') else window._board_widget.move_made, timeout=3000, raising=False) as blocker:
        window._new_game("black")
        
        assert window._player_color == "black"
        assert window._status.currentMessage() == "Engine is thinking..."
        assert window._board_widget.isEnabled() is False
        assert window._worker is not None
        
        # Wait for worker thread to complete its run and emit move_found
        qtbot.waitSignal(window._worker.move_found, timeout=3000)
    
    # After engine moves
    assert window._board_widget.isEnabled() is True
    assert "Your move" in window._status.currentMessage()
    assert window._worker is None
    assert window._board_widget.board.turn == "black" # It's now black's turn
