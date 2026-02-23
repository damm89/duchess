import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent
from duchess.gui.board_widget import ChessBoardWidget, PieceItem
from duchess.gui.worker import EngineWorker

def test_board_widget_crash_resilience(qtbot):
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)

    event_view = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100.0, 100.0),
        QPointF(100.0, 100.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    # Force _handle_square_click to raise an exception
    with patch.object(widget, '_handle_square_click', side_effect=ValueError("Test view crash")):
        with patch('traceback.print_exc') as mock_print_exc:
            # Should not raise an exception or crash
            widget.mousePressEvent(event_view)
            mock_print_exc.assert_called_once()


def test_piece_item_crash_resilience(qtbot):
    widget = ChessBoardWidget()
    qtbot.addWidget(widget)
    
    widget.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    
    assert len(widget._piece_items) > 0
    piece_item = widget._piece_items[0]
    
    event_scene = MagicMock()
    event_scene.button.return_value = Qt.MouseButton.LeftButton
    event_scene.scenePos.return_value = QPointF(100, 100)
    
    # Force an exception in a deep method called by PieceItem.mousePressEvent
    with patch.object(widget, '_set_selected', side_effect=RuntimeError("Test piece crash")):
        with patch('traceback.print_exc') as mock_print_exc:
            piece_item.mousePressEvent(event_scene)
            mock_print_exc.assert_called_once()


def test_engine_worker_crash_resilience():
    # Provide a simple FEN
    worker = EngineWorker(fen="8/8/8/8/8/8/8/8 w - - 0 1", time_ms=10)
    
    # Mock the engine method called in run() to throw an exception
    with patch('duchess.engine.ChessEngine.get_best_move_timed', side_effect=ValueError("Test worker crash")):
        with patch('traceback.print_exc') as mock_print_exc:
            # Should catch the error internally and not crash the thread test
            worker.run()
            mock_print_exc.assert_called_once()
