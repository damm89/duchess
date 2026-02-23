"""Tests for the Opening Explorer — Lichess API client and GUI widget."""
import pytest
from unittest.mock import patch, MagicMock

from duchess.lichess_api import LichessExplorerClient


# --- Sample Lichess API response (truncated) ---

SAMPLE_RESPONSE = {
    "white": 933863,
    "draws": 1271743,
    "black": 673981,
    "moves": [
        {
            "uci": "e2e4", "san": "e4", "averageRating": 2396,
            "white": 419328, "draws": 573290, "black": 316848,
            "game": None,
            "opening": {"eco": "B00", "name": "King's Pawn Game"},
        },
        {
            "uci": "d2d4", "san": "d4", "averageRating": 2409,
            "white": 334470, "draws": 461840, "black": 233568,
            "game": None,
            "opening": {"eco": "A40", "name": "Queen's Pawn Game"},
        },
    ],
    "topGames": [],
    "opening": None,
}

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# --- LichessExplorerClient tests ---

class TestLichessExplorerClient:

    def test_parse_response(self):
        """Verify the parser extracts moves with correct fields and percentages."""
        result = LichessExplorerClient._parse(SAMPLE_RESPONSE)

        assert result["total"] == 933863 + 1271743 + 673981
        assert result["opening"] is None  # starting position has no opening
        moves = result["moves"]
        assert len(moves) == 2

        e4 = moves[0]
        assert e4["san"] == "e4"
        assert e4["uci"] == "e2e4"
        assert e4["avg_rating"] == 2396
        assert e4["opening_eco"] == "B00"
        assert e4["opening_name"] == "King's Pawn Game"
        total_e4 = 419328 + 573290 + 316848
        assert e4["total"] == total_e4
        assert e4["win_pct"] == round(100 * 419328 / total_e4, 1)
        assert e4["draw_pct"] == round(100 * 573290 / total_e4, 1)
        assert e4["loss_pct"] == round(100 * 316848 / total_e4, 1)

    def test_parse_with_opening(self):
        """Verify opening name is extracted when present."""
        data = dict(SAMPLE_RESPONSE)
        data["opening"] = {"eco": "C50", "name": "Italian Game"}
        result = LichessExplorerClient._parse(data)
        assert result["opening"] == "C50 · Italian Game"

    @patch("duchess.lichess_api.requests.Session")
    def test_query_caches_results(self, MockSession):
        """Same FEN queried twice should only make one HTTP call."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        MockSession.return_value = mock_session

        client = LichessExplorerClient()
        result1 = client.query(START_FEN)
        result2 = client.query(START_FEN)

        assert result1 == result2
        assert mock_session.get.call_count == 1  # only one HTTP call

    @patch("duchess.lichess_api.requests.Session")
    def test_query_handles_network_error(self, MockSession):
        """Network errors should return an empty result, never raise."""
        import requests as req_lib
        mock_session = MagicMock()
        mock_session.get.side_effect = req_lib.ConnectionError("offline")
        MockSession.return_value = mock_session

        client = LichessExplorerClient()
        result = client.query(START_FEN)

        assert result["total"] == 0
        assert result["moves"] == []
        assert result["opening"] is None

    @patch("duchess.lichess_api.requests.Session")
    def test_query_handles_bad_json(self, MockSession):
        """Invalid JSON from API should return an empty result."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("bad json")
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        MockSession.return_value = mock_session

        client = LichessExplorerClient()
        result = client.query(START_FEN)

        assert result["total"] == 0
        assert result["moves"] == []

    def test_clear_cache(self):
        """Verify clear_cache empties the internal cache."""
        client = LichessExplorerClient()
        client._cache["some_fen"] = {"total": 1, "moves": [], "opening": None}
        assert len(client._cache) == 1
        client.clear_cache()
        assert len(client._cache) == 0


# --- OpeningExplorerWidget tests ---

class TestOpeningExplorerWidget:

    def test_widget_initialization(self, qtbot):
        """Widget should instantiate and have the correct table headers."""
        from duchess.gui.opening_explorer import OpeningExplorerWidget
        widget = OpeningExplorerWidget()
        qtbot.addWidget(widget)

        table = widget._table
        assert table.columnCount() == 5
        headers = [table.horizontalHeaderItem(c).text() for c in range(5)]
        assert headers == ["Move", "Games", "Score", "Rating", "Opening"]

    def test_widget_populates_table(self, qtbot):
        """Calling _on_results directly should populate the table rows."""
        from duchess.gui.opening_explorer import OpeningExplorerWidget
        widget = OpeningExplorerWidget()
        qtbot.addWidget(widget)

        parsed = LichessExplorerClient._parse(SAMPLE_RESPONSE)
        widget._on_results(parsed)

        assert widget._table.rowCount() == 2
        assert widget._table.item(0, 0).text() == "e4"
        assert widget._table.item(1, 0).text() == "d4"

    def test_widget_emits_move_clicked(self, qtbot):
        """Double-clicking a row should emit the move_clicked signal."""
        from duchess.gui.opening_explorer import OpeningExplorerWidget
        widget = OpeningExplorerWidget()
        qtbot.addWidget(widget)

        parsed = LichessExplorerClient._parse(SAMPLE_RESPONSE)
        widget._on_results(parsed)

        with qtbot.waitSignal(widget.move_clicked, timeout=1000) as blocker:
            widget._on_cell_double_clicked(0, 0)

        assert blocker.args[0] == "e2e4"

    def test_widget_empty_results(self, qtbot):
        """Empty result should show 0 rows and 'not in database' label."""
        from duchess.gui.opening_explorer import OpeningExplorerWidget
        widget = OpeningExplorerWidget()
        qtbot.addWidget(widget)

        widget._on_results({"opening": None, "total": 0, "moves": []})

        assert widget._table.rowCount() == 0
        assert "not in database" in widget._opening_label.text().lower()
