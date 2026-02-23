import pytest
from PyQt6.QtCore import Qt, QPoint, QPointF
from duchess.gui.board_widget import ChessBoardWidget, SQ_SIZE, _sq_to_scene


def _sq_to_viewport_pos(widget, sq):
    """Convert a square index to a viewport QPoint for clicking."""
    scene_pt = _sq_to_scene(sq) + QPointF(SQ_SIZE / 2, SQ_SIZE / 2)
    view_pt = widget.mapFromScene(scene_pt)
    return QPoint(int(view_pt.x()), int(view_pt.y()))


def test_interactive_move_e2e4(qtbot):
    """Simulate clicking on e2 and e4 to play 1. e4."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    widget.resize(640, 640)
    widget.show()
    qtbot.waitExposed(widget)

    pos_e2 = _sq_to_viewport_pos(widget, 12)  # e2
    pos_e4 = _sq_to_viewport_pos(widget, 28)  # e4

    # 1. Click e2
    qtbot.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos_e2)
    assert widget._selected_sq == 12, f"Selected square should be 12 (e2), got {widget._selected_sq}"

    # 2. Click e4
    with qtbot.waitSignal(widget.move_made, timeout=1000) as blocker:
        qtbot.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos_e4)

    assert blocker.args[0] == "e2e4"
    assert "e4" in blocker.args[1]  # SAN
    assert widget.board.turn == "black"
    assert widget._last_move_from == 12
    assert widget._last_move_to == 28


def test_illegal_move_discarded(qtbot):
    """Simulate an illegal move (e2-e5)."""
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    widget.resize(640, 640)
    widget.show()
    qtbot.waitExposed(widget)

    pos_e2 = _sq_to_viewport_pos(widget, 12)  # e2
    pos_e5 = _sq_to_viewport_pos(widget, 36)  # e5

    qtbot.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos_e2)
    qtbot.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos_e5)

    # Move should NOT be made. Selection should be cleared.
    assert widget.board.turn == "white"
    assert widget._selected_sq is None
