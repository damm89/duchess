from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from duchess.gui.board_widget import ChessBoardWidget, PieceItem
from PyQt6.QtGui import QMouseEvent, QWindow
from PyQt6.QtTest import QTest
import sys

app = QApplication(sys.argv)
widget = ChessBoardWidget()

# Print methods of QMouseEvent
def test_qmouseevent(e):
    print("In proxy event!")
    print(f"e.pos() = {hasattr(e, 'pos')}")
    if hasattr(e, 'pos'):
        try:
            print(f"e.pos() call: {e.pos()}")
        except Exception as ex:
            print(f"e.pos() raised {ex}")
    
    print(f"e.position() = {hasattr(e, 'position')}")
    if hasattr(e, 'position'):
        try:
            print(f"e.position() call: {e.position()}")
        except Exception as ex:
            print(f"e.position() raised {ex}")

# We'll monkeypatch to see what happens
orig_mp = ChessBoardWidget.mousePressEvent
def mp_proxy(self, event):
    test_qmouseevent(event)
    orig_mp(self, event)
ChessBoardWidget.mousePressEvent = mp_proxy

orig_piece_mp = PieceItem.mousePressEvent
def piece_mp_proxy(self, event):
    print("In piece proxy event!")
    print(f"event.pos() = {hasattr(event, 'pos')}")
    if hasattr(event, 'pos'):
        try:
            print(f"event.pos() call: {event.pos()}")
        except Exception as ex:
            print(f"event.pos() raised {ex}")
    orig_piece_mp(self, event)
PieceItem.mousePressEvent = piece_mp_proxy

widget.show()

# click empty square
print("Clicking empty square...")
QTest.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, 100))

# click piece. There's a piece at (40, 40) because it's square a1 initially
print("Clicking piece...")
QTest.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(40, 600))

app.quit()
sys.exit(0)
