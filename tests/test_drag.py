import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

view = window._board_widget

print("Finding e2 pawn...")
for item in view._piece_items:
    if item._sq == 12: # e2
        e2_pawn = item
        break

print("Simulating drag...")
import traceback
try:
    # 1. Press
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(360, 520), QPointF(360, 520),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    e2_pawn.mousePressEvent(press_event)
    print("Dragging state after press:", e2_pawn._dragging)
    
    # 2. Move
    scene_pos = QPointF(360, 360)
    class MockEvent:
        def scenePos(self): return scene_pos
    e2_pawn.mouseMoveEvent(MockEvent())
    
    # 3. Release
    e2_pawn.mouseReleaseEvent(MockEvent())
    print("Dragging state after release:", e2_pawn._dragging)
except Exception as e:
    traceback.print_exc()

print("Drag simulation done.")
sys.exit(0)
