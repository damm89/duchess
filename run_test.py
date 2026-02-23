from PyQt6.QtWidgets import QApplication
from duchess.gui.main_window import DuchessMainWindow
import sys
app = QApplication(sys.argv)
win = DuchessMainWindow()
win.show()
sys.exit(app.exec())
