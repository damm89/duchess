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
        print(f"\n[BOARD] PUSH_UCI CALLED WITH MOVE: {uci}")
        print(f"[BOARD] FEN before: {view.board.fen()}")
        orig_push_uci(uci)
        print(f"[BOARD] FEN after: {view.board.fen()}\n")
    view.board.push_uci = tracing_push_uci
    
    orig_sync = view.board._sync_engine
    def tracing_sync():
        print("[BOARD] Snycing engine position")
        orig_sync()
    view.board._sync_engine = tracing_sync

    # Hook move_made emit
    orig_emit = view.move_made.emit
    def tracing_emit(uci, san):
        print(f"[WIDGET] MOVE_MADE SIGNAL EMITTED: {uci} -> {san}")
        orig_emit(uci, san)
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

    QTest.qWait(1000)

    print("Done")

if __name__ == "__main__":
    run_test()
