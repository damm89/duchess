"""Tests for Phase 5.1 (QGraphicsScene board), 5.2 (eval bar, PV arrows, info parsing),
and 5.3 (multi-engine analysis panel)."""
import pytest
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem

from duchess.gui.board_widget import (
    ChessBoardWidget, PieceItem, SQ_SIZE,
    _sq_to_scene, _scene_to_sq, _is_own_piece,
)
from duchess.gui.eval_bar import EvaluationBar
from duchess.gui.main_window import MainWindow
from duchess.gui.worker import EngineWorker
from duchess.engine_wrapper import _parse_info_line, UCIEngine
from duchess.chess_types import Piece


# ---------------------------------------------------------------------------
# Phase 5.1: QGraphicsView board
# ---------------------------------------------------------------------------

class TestBoardGraphicsScene:
    def test_inherits_qgraphicsview(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        assert isinstance(widget, QGraphicsView)

    def test_scene_created(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        assert isinstance(widget._scene, QGraphicsScene)
        assert widget._scene.sceneRect().width() == 8 * SQ_SIZE
        assert widget._scene.sceneRect().height() == 8 * SQ_SIZE

    def test_64_square_items(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        assert len(widget._square_items) == 64
        for item in widget._square_items:
            assert isinstance(item, QGraphicsRectItem)

    def test_32_pieces_at_start(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        assert len(widget._piece_items) == 32
        for item in widget._piece_items:
            assert isinstance(item, PieceItem)

    def test_piece_count_after_set_fen(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        # Endgame: just two kings
        widget.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert len(widget._piece_items) == 2

    def test_sq_to_scene_a1(self):
        pos = _sq_to_scene(0)  # a1
        assert pos.x() == 0
        assert pos.y() == 7 * SQ_SIZE  # bottom row

    def test_sq_to_scene_h8(self):
        pos = _sq_to_scene(63)  # h8
        assert pos.x() == 7 * SQ_SIZE
        assert pos.y() == 0  # top row

    def test_scene_to_sq_roundtrip(self):
        for sq in range(64):
            pos = _sq_to_scene(sq) + QPointF(SQ_SIZE / 2, SQ_SIZE / 2)
            assert _scene_to_sq(pos) == sq

    def test_scene_to_sq_out_of_bounds(self):
        # Far beyond the board edge
        assert _scene_to_sq(QPointF(8 * SQ_SIZE + 10, 0)) is None
        assert _scene_to_sq(QPointF(0, 8 * SQ_SIZE + 10)) is None

    def test_highlights_clear_on_set_fen(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        widget._selected_sq = 10
        widget._last_move_from = 12
        widget._last_move_to = 28
        widget.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert widget._selected_sq is None
        assert widget._last_move_from is None
        assert widget._last_move_to is None


# ---------------------------------------------------------------------------
# Phase 5.2: Eval bar
# ---------------------------------------------------------------------------

class TestEvalBar:
    def test_init_defaults(self, qtbot):
        bar = EvaluationBar()
        qtbot.addWidget(bar)
        assert bar._score_cp == 0
        assert bar._mate is None
        assert bar.width() == 28

    def test_set_score_cp(self, qtbot):
        bar = EvaluationBar()
        qtbot.addWidget(bar)
        bar.set_score(cp=200, depth=5)
        assert bar._score_cp == 200
        assert bar._mate is None
        assert bar._depth == 5

    def test_set_score_mate(self, qtbot):
        bar = EvaluationBar()
        qtbot.addWidget(bar)
        bar.set_score(mate=3, depth=10)
        assert bar._mate == 3
        assert bar._depth == 10

    def test_set_score_resets_mate(self, qtbot):
        bar = EvaluationBar()
        qtbot.addWidget(bar)
        bar.set_score(mate=2)
        bar.set_score(cp=50)
        # mate should be reset to None when setting cp
        assert bar._mate is None
        assert bar._score_cp == 50


# ---------------------------------------------------------------------------
# Phase 5.2: PV arrows
# ---------------------------------------------------------------------------

class TestPVArrows:
    def test_draw_arrows(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        widget.draw_pv_arrows(["e2e4", "e7e5", "g1f3"])
        assert len(widget._arrow_items) == 3

    def test_clear_arrows(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        widget.draw_pv_arrows(["e2e4", "e7e5"])
        assert len(widget._arrow_items) == 2
        widget.clear_arrows()
        assert len(widget._arrow_items) == 0

    def test_draw_arrows_replaces_old(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        widget.draw_pv_arrows(["e2e4", "e7e5"])
        widget.draw_pv_arrows(["d2d4"])
        assert len(widget._arrow_items) == 1

    def test_draw_arrows_skips_short_uci(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        widget.draw_pv_arrows(["e2", "e2e4"])
        assert len(widget._arrow_items) == 1

    def test_set_fen_clears_arrows(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        widget.draw_pv_arrows(["e2e4"])
        widget.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert len(widget._arrow_items) == 0


# ---------------------------------------------------------------------------
# Phase 5.2: UCI info line parsing
# ---------------------------------------------------------------------------

class TestInfoLineParsing:
    def test_parse_full_info_line(self):
        info = _parse_info_line(
            "info depth 8 score cp 35 nodes 12345 time 200 nps 61725 pv e2e4 e7e5 g1f3"
        )
        assert info["depth"] == 8
        assert info["score_cp"] == 35
        assert info["nodes"] == 12345
        assert info["time"] == 200
        assert info["nps"] == 61725
        assert info["pv"] == ["e2e4", "e7e5", "g1f3"]

    def test_parse_mate_score(self):
        info = _parse_info_line("info depth 12 score mate 3 nodes 50000 pv g5g7")
        assert info["score_mate"] == 3
        assert "score_cp" not in info
        assert info["pv"] == ["g5g7"]

    def test_parse_negative_cp(self):
        info = _parse_info_line("info depth 5 score cp -120 nodes 800 pv d7d5")
        assert info["score_cp"] == -120

    def test_parse_no_pv(self):
        info = _parse_info_line("info depth 1 score cp 0 nodes 20")
        assert info["depth"] == 1
        assert info["score_cp"] == 0
        assert "pv" not in info


# ---------------------------------------------------------------------------
# Phase 5.3: UCIEngine name capture
# ---------------------------------------------------------------------------

class TestEngineNameCapture:
    def test_duchess_engine_has_name(self):
        try:
            engine = UCIEngine()
        except FileNotFoundError:
            pytest.skip("duchess_cli not built")
        assert engine.name == "Duchess"
        engine.quit()

    def test_engine_accepts_engine_path(self):
        import inspect
        sig = inspect.signature(UCIEngine.__init__)
        assert "engine_path" in sig.parameters


# ---------------------------------------------------------------------------
# Phase 5.3: Analysis panel
# ---------------------------------------------------------------------------

class TestAnalysisPanel:
    def test_duchess_row_exists_at_init(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert len(window._control_panel._analysis_rows) == 1
        from duchess.engine_wrapper import get_engine
        assert get_engine().name in window._control_panel._analysis_rows

    def test_add_analysis_row(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window._add_analysis_row("Stockfish 16")
        assert "Stockfish 16" in window._control_panel._analysis_rows
        assert len(window._control_panel._analysis_rows) == 2

    def test_search_info_updates_duchess_row(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        from duchess.engine_wrapper import get_engine
        duchess_name = get_engine().name
        window._on_search_info(duchess_name, {
            "depth": 7,
            "score_cp": 55,
            "nodes": 5000,
            "nps": 25000,
            "pv": ["e2e4", "e7e5"],
        })
        row = window._control_panel.get_analysis_row(duchess_name)
        assert row["depth"].text() == "d7"
        assert row["score"].text() == "+0.55"
        assert "e2e4" in row["pv"].text()

    def test_search_info_updates_external_row(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window._add_analysis_row("Stockfish 16")
        window._on_search_info("Stockfish 16", {
            "depth": 15,
            "score_cp": -80,
            "pv": ["d2d4", "d7d5", "c2c4"],
        })
        row = window._control_panel.get_analysis_row("Stockfish 16")
        assert row["depth"].text() == "d15"
        assert row["score"].text() == "-0.80"
        assert "d2d4" in row["pv"].text()

    def test_duchess_info_updates_eval_bar(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        from duchess.engine_wrapper import get_engine
        window._on_search_info(get_engine().name, {
            "depth": 5,
            "score_cp": 150,
            "pv": ["e2e4"],
        })
        assert window._eval_bar._score_cp == 150

    def test_external_info_does_not_update_eval_bar(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window._eval_bar.set_score(cp=0)
        window._add_analysis_row("Stockfish 16")
        window._on_search_info("Stockfish 16", {
            "depth": 10,
            "score_cp": -300,
            "pv": ["d2d4"],
        })
        # Eval bar should still show 0, not -300
        assert window._eval_bar._score_cp == 0

    def test_external_engine_move_ignored(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window._new_game("white")
        initial_fen = window._board_widget.board.fen()
        # Simulate an external engine emitting a move — should be ignored
        window._on_engine_move("e7e5", "Stockfish 16")
        assert window._board_widget.board.fen() == initial_fen

    def test_new_game_resets_analysis_rows(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        from duchess.engine_wrapper import get_engine
        duchess_name = get_engine().name
        # Simulate some info
        window._on_search_info(duchess_name, {
            "depth": 10, "score_cp": 200, "pv": ["e2e4"],
        })
        row = window._control_panel.get_analysis_row(duchess_name)
        assert row["depth"].text() != "--"
        # New game resets
        window._new_game("white")
        assert row["depth"].text() == "--"
        assert row["score"].text() == "--"
        assert row["pv"].text() == ""

    def test_right_panel_fixed_width(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        # Find the right panel — it should have a fixed width of 300
        central = window.centralWidget()
        layout = central.layout()
        # Right panel is the last widget in the HBox (after eval bar and board)
        right_panel = layout.itemAt(layout.count() - 1).widget()
        assert right_panel.maximumWidth() == 300
        assert right_panel.minimumWidth() == 300


# ---------------------------------------------------------------------------
# Phase 5.3: Worker signals include engine name
# ---------------------------------------------------------------------------

class TestWorkerSignals:
    def test_worker_emits_name_with_move(self, qtbot):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        worker = EngineWorker(fen, time_ms=200)

        with qtbot.waitSignal(worker.move_found, timeout=3000) as blocker:
            worker.start()

        uci_move = blocker.args[0]
        engine_name = blocker.args[1]
        assert len(uci_move) >= 4
        assert isinstance(engine_name, str)
        assert len(engine_name) > 0
        worker.wait()

    def test_worker_emits_search_info(self, qtbot):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        worker = EngineWorker(fen, time_ms=500)

        with qtbot.waitSignal(worker.search_info, timeout=3000) as blocker:
            worker.start()

        name = blocker.args[0]
        info = blocker.args[1]
        assert isinstance(name, str)
        assert isinstance(info, dict)
        assert "depth" in info
        worker.wait()
