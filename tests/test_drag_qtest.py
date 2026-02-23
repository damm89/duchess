import pytest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

def run_test():
    app = QApplication(sys.argv)
    window = MainWindow()
    window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

    view = window._board_widget
    view.show()

    print("Finding e2 pawn...")
    e2_pawn = next(item for item in view._piece_items if item._sq == 12)

    # Wrap methods to trace
    orig_press = e2_pawn.mousePressEvent
    def tracing_press(e):
        print("Press Event!")
        print("  dragging state before: ", e2_pawn._dragging)
        orig_press(e)
        print("  dragging state after: ", e2_pawn._dragging)
    e2_pawn.mousePressEvent = tracing_press

    orig_move = e2_pawn.mouseMoveEvent
    def tracing_move(e):
        print("Move Event!")
        orig_move(e)
    e2_pawn.mouseMoveEvent = tracing_move

    orig_release = e2_pawn.mouseReleaseEvent
    def tracing_release(e):
        print("Release Event!")
        orig_release(e)
    e2_pawn.mouseReleaseEvent = tracing_release
    
    # 1. Press and hold on e2 pawn (360, 520)
    print("Mouse press e2 pawn")
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 520))

    # 2. Move to e4 square (360, 360)
    print("Mouse move to e4")
    QTest.mouseMove(view.viewport(), QPoint(360, 360))

    # 3. Release on e4 square
    print("Mouse release on e4")
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))

    print("Done")

if __name__ == "__main__":
    run_test()
