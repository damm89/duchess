import pytest
from PyQt6.QtCore import Qt, QPoint
from duchess.gui.board_widget import ChessBoardWidget
from duchess.chess_types import Piece

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

def test_board_widget_scene_to_square(qtbot):
    """Test the internal scene pos to square calculation."""
    from duchess.gui.board_widget import _scene_to_sq, SQ_SIZE
    from PyQt6.QtCore import QPointF
    
    # Click on bottom-left corner -> a1 (index 0)
    # The rank 1 is at the bottom, which is rank_idx = 7 in the widget.
    
    sq = _scene_to_sq(QPointF(1, 7 * SQ_SIZE + 1))
    assert sq == 0

    # Click on top-right corner -> h8 (index 63)
    # The rank 8 is at the top, which is rank_idx = 0. File h is file_idx = 7.
    sq = _scene_to_sq(QPointF(7 * SQ_SIZE + 1, 1))
    assert sq == 63
