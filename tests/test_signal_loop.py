import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from duchess.gui.main_window import MainWindow

def run_test():
    app = QApplication(sys.argv)
    window = MainWindow()
    window._board_widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    window.show()

    # We want to see how many times worker is started
    orig_start = window._start_engine
    start_count = 0
    def tracing_start():
        nonlocal start_count
        start_count += 1
        print(f"MAIN_WINDOW START_ENGINE called (count: {start_count})")
        orig_start()
    window._start_engine = tracing_start
    


    # Track move signal
    emit_count = 0
    def tracing_emit(uci, san):
        nonlocal emit_count
        emit_count += 1
        print(f"MOVE_MADE SIGNAL EMITTED (count: {emit_count}): {uci} -> {san}")
    window._board_widget.move_made.connect(tracing_emit)

    print("Finding e2 pawn...")
    view = window._board_widget
    e2_pawn = next(item for item in view._piece_items if item._sq == 12)

    print("Executing UI sequence")
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 520))
    QTest.mouseMove(view.viewport(), QPoint(360, 360))
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 360))

    QTest.qWait(1000)
    print("Test finished.")

if __name__ == "__main__":
    run_test()
