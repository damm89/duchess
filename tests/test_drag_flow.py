import pytest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

def test_drag_and_drop_flow():
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

    view = window._board_widget
    view.show()

    emit_count = 0
    def tracing_emit(uci, san):
        nonlocal emit_count
        emit_count += 1
    view.move_made.connect(tracing_emit)
    
    e2_pawn = next(item for item in view._piece_items if item._sq == 12)
    orig_pos = e2_pawn.pos()

    # Drag e2 pawn
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 520))
    QTest.mouseMove(view.viewport(), QPoint(360, 360))
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))

    QTest.qWait(100)

    # Valid move should emit exactly 1 move_made
    assert emit_count == 1, f"Expected 1 move emission but got {emit_count}"
    assert e2_pawn not in view._scene.items(), "Pieces should have been completely re-synced after move"
    
    # Try invalid move (e4 pawn to e6)
    emit_count = 0
    e4_pawn = next(item for item in view._piece_items if item._sq == 28)
    e4_pos = e4_pawn.pos()
    
    # Drag e4 pawn to e6
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))
    QTest.mouseMove(view.viewport(), QPoint(360, 200))
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 200))
    
    QTest.qWait(100)

    assert emit_count == 0, "Invalid back-to-back move should not emit"

if __name__ == "__main__":
    test_drag_and_drop_flow()
    print("All tests passed.")
