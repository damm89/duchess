import pytest
from PyQt6.QtCore import Qt, QPoint
from duchess.gui.board_widget import ChessBoardWidget

def test_interactive_move_e2e4(qtbot):
    """Simulate clicking on e2 and e4 to play 1. e4."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    widget.resize(640, 640)
    
    sq_size, x_off, y_off = widget._board_geometry()
    
    # e2 is: file=4, rank=2. In widget rank_idx = 6
    x_e = x_off + 4 * sq_size + sq_size / 2
    y_2 = y_off + 6 * sq_size + sq_size / 2
    pos_e2 = QPoint(int(x_e), int(y_2))
    
    # e4 is: file=4, rank=4. In widget rank_idx = 4
    y_4 = y_off + 4 * sq_size + sq_size / 2
    pos_e4 = QPoint(int(x_e), int(y_4))
    
    # 1. Click e2
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=pos_e2)
    assert widget._selected_sq == 12, f"Selected square should be 12 (e2), got {widget._selected_sq}"
    
    # 2. Click e4
    with qtbot.waitSignal(widget.move_made, timeout=1000) as blocker:
        qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=pos_e4)
        
    assert blocker.args[0] == "e2e4"
    assert "e4" in blocker.args[1]  # SAN might be 'e4'
    assert widget.board.turn == "black"
    assert widget._last_move_from == 12
    assert widget._last_move_to == 28


def test_illegal_move_discarded(qtbot):
    """Simulate an illegal move (e2-e5)."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    widget.resize(640, 640)
    
    sq_size, x_off, y_off = widget._board_geometry()
    
    x_e = x_off + 4 * sq_size + sq_size / 2
    y_2 = y_off + 6 * sq_size + sq_size / 2
    pos_e2 = QPoint(int(x_e), int(y_2))
    
    # e5 is: file=4, rank=5. In widget rank_idx = 3
    y_5 = y_off + 3 * sq_size + sq_size / 2
    pos_e5 = QPoint(int(x_e), int(y_5))
    
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=pos_e2)
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=pos_e5)
    
    # Move should NOT be made. e2 selection should be cleared.
    assert widget.board.turn == "white"
    assert widget._selected_sq is None
