import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

view = window._board_widget
view.show()

print("Finding e2 pawn...")
e2_pawn = next(item for item in view._piece_items if item._sq == 12)

print("e2 pawn scale:", e2_pawn.scale())
print("e2 pawn bounds:", e2_pawn.boundingRect())
print("e2 pawn pos:", e2_pawn.pos())

# Wrap methods to trace
orig_press = e2_pawn.mousePressEvent
def tracing_press(e):
    print("Press Event!")
    print("  pos():", e.pos())
    print("  scenePos():", e.scenePos())
    orig_press(e)
e2_pawn.mousePressEvent = tracing_press

orig_move = e2_pawn.mouseMoveEvent
def tracing_move(e):
    print("Move Event!")
    print("  pos():", getattr(e, 'pos', lambda: None)())
    print("  scenePos():", getattr(e, 'scenePos', lambda: None)())
    orig_move(e)
e2_pawn.mouseMoveEvent = tracing_move

orig_release = e2_pawn.mouseReleaseEvent
def tracing_release(e):
    print("Release Event!")
    print("  scenePos():", getattr(e, 'scenePos', lambda: None)())
    orig_release(e)
e2_pawn.mouseReleaseEvent = tracing_release

print("--- Simulating UI interaction ---")
# 1. Press
press_event = QGraphicsSceneMouseEvent(QGraphicsSceneMouseEvent.Type.GraphicsSceneMousePress)
press_event.setButton(Qt.MouseButton.LeftButton)
press_event.setScenePos(QPointF(360, 520))
press_event.setPos(QPointF(36, 36)) # arbitrary local pos

e2_pawn.sceneEvent(press_event)
print("Dragging state after press:", e2_pawn._dragging)
print("_drag_offset:", e2_pawn._drag_offset)

# 2. Move
move_event = QGraphicsSceneMouseEvent(QGraphicsSceneMouseEvent.Type.GraphicsSceneMouseMove)
move_event.setScenePos(QPointF(360, 360))
e2_pawn.sceneEvent(move_event)
print("Pawn pos after move:", e2_pawn.pos())

# 3. Release
release_event = QGraphicsSceneMouseEvent(QGraphicsSceneMouseEvent.Type.GraphicsSceneMouseRelease)
release_event.setScenePos(QPointF(360, 360))
e2_pawn.sceneEvent(release_event)

print("Drag simulation done.")
sys.exit(0)
