import pytest
from PyQt6.QtCore import Qt, QPoint
from duchess.gui.board_widget import ChessBoardWidget
from duchess_engine import Piece

# Using pytest-qt's qtbot fixture to test PyQt6 components
def test_board_widget_initialization(qtbot):
    """Test that the widget can be instantiated and the default FEN is applied."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    
    # Check minimum size
    assert widget.minimumWidth() >= 320
    assert widget.minimumHeight() >= 320

def test_board_widget_set_fen(qtbot):
    """Test parsing a FEN updates the internal board structure."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    
    # A simple endgame FEN
    test_fen = "8/8/8/8/8/8/4K3/8 w - - 0 1"
    widget.set_fen(test_fen)
    
    # Internal DuchessBoard is updated
    assert widget.board.turn == "white"
    
    # Check square 'e2' which is square 12 (0-indexed a1=0, b1=1... e2=12)
    # File 'e' is index 4. Rank 2 is index 1. sq = 1 * 8 + 4 = 12
    piece_at_e2 = widget.board.piece_at_sq(12)
    assert piece_at_e2 == Piece.WHITE_KING

def test_board_widget_pixel_to_square(qtbot):
    """Test the internal pixel to square calculation."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    
    # Force a resize to simulate a window
    widget.resize(600, 600)
    
    sq_size, x_off, y_off = widget._board_geometry()
    
    # Click on bottom-left corner -> a1 (index 0)
    # The rank 1 is at the bottom, which is rank_idx = 7 in the widget.
    # So y coordinate should be y_off + 7 * sq_size + 1
    # x coordinate should be x_off + 1
    click_x = x_off + 1
    click_y = y_off + 7 * sq_size + 1
    
    sq = widget._pixel_to_square(click_x, click_y)
    assert sq == 0

    # Click on top-right corner -> h8 (index 63)
    # The rank 8 is at the top, which is rank_idx = 0. File h is file_idx = 7.
    click_x = x_off + 7 * sq_size + 1
    click_y = y_off + 1
    sq = widget._pixel_to_square(click_x, click_y)
    assert sq == 63
