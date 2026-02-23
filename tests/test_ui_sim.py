import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

def test_full_app_clicks(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Give it a fen
    window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    
    view = window._board_widget
    
    # Click empty square (e4 is at rank index 4, file index 4. e4 = sq 28)
    # y = 4 * 80 = 320, x = 4 * 80 = 320
    print("Clicking empty square...")
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))
    
    # Click piece on e2 (rank index 6, file index 4. e2 = sq 12)
    # y = 6 * 80 = 480, x = 4 * 80 = 320
    print("Clicking e2 pawn...")
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 520))
    
    # Click empty square e4
    print("Clicking e4 square to move pawn...")
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))
    window.close()

