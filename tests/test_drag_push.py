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

    # Hook the board's push_uci method to see if the move makes it to the engine
    orig_push_uci = view.board.push_uci
    def tracing_push_uci(uci):
        print(f"BOARD PUSH_UCI CALLED WITH MOVE: {uci}")
        orig_push_uci(uci)
    view.board.push_uci = tracing_push_uci
    
    # Hook move_made emit
    def tracing_emit(uci, san):
        print(f"MOVE_MADE SIGNAL EMITTED: {uci} -> {san}")
    view.move_made.connect(tracing_emit)
        
    print("Finding e2 pawn...")
    e2_pawn = next(item for item in view._piece_items if item._sq == 12)

    print("Mouse press e2 pawn")
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 520))

    print("Mouse move to e4")
    QTest.mouseMove(view.viewport(), QPoint(360, 360))

    print("Mouse release on e4")
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))
    print(f"Dragged pawn final position: {e2_pawn.pos()}")

    print("Done")

if __name__ == "__main__":
    run_test()
