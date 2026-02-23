import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

def test_full_app_clicks(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    view = window._board_widget
    
    # Drag piece on e2 (rank index 6, file index 4. e2 = sq 12)
    e2_pawn = next(item for item in view._piece_items if item._sq == 12)
    print("Found e2 pawn, starting drag")
    
    # 1. Press
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(360, 520),
        QPointF(360, 520),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    e2_pawn.sceneEvent(press_event)
    print("Dragging state after press:", e2_pawn._dragging)
    
    # 2. Move
    class MockEvent:
        def __init__(self, pos):
            self._pos = pos
        def scenePos(self): return self._pos
        def type(self): return QMouseEvent.Type.MouseMove
    move_event = MockEvent(QPointF(360, 360))
    try:
        e2_pawn.mouseMoveEvent(move_event)
    except Exception:
        import traceback
        traceback.print_exc()
        
    # 3. Release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(360, 360),
        QPointF(360, 360),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    e2_pawn.sceneEvent(release_event)
    print("Dragging state after release:", e2_pawn._dragging)
    
    # Wait to see if engine responds
    qtbot.wait(100)
    print("Done")
    window.close()
