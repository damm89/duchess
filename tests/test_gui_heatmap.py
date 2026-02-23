"""GUI tests for the threat heatmap feature."""
import pytest
from PyQt6.QtCore import Qt
from duchess.gui.board_widget import ChessBoardWidget
from duchess.gui.main_window import MainWindow
from duchess.chess_types import Piece


class TestBoardWidgetHeatmap:
    def test_heatmap_overlays_exist(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        assert len(widget._heatmap_items) == 64

    def test_heatmap_overlays_initially_invisible(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)
        for overlay in widget._heatmap_items:
            assert overlay.isVisible() is False

    def test_set_heatmap_makes_overlays_visible(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)

        # Create simple attack data: white attacks sq 0 more, black attacks sq 63 more
        white_attacks = [2] + [0] * 63
        black_attacks = [0] * 63 + [2]
        widget.set_heatmap(white_attacks, black_attacks, "white")

        # sq 0 should be visible (white controls it = friendly = blue)
        assert widget._heatmap_items[0].isVisible() is True
        # sq 63 should be visible (black controls it = hostile = red)
        assert widget._heatmap_items[63].isVisible() is True
        # A neutral square should be invisible
        assert widget._heatmap_items[32].isVisible() is False

    def test_set_heatmap_respects_player_color(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)

        # If player is black, white attacks are hostile (red), black attacks are friendly (blue)
        white_attacks = [3] + [0] * 63
        black_attacks = [0] * 64
        widget.set_heatmap(white_attacks, black_attacks, "black")

        # sq 0 is attacked more by white — for a black player, that's hostile (red)
        overlay = widget._heatmap_items[0]
        assert overlay.isVisible() is True
        color = overlay.brush().color()
        assert color.red() > color.blue()  # red tint

    def test_clear_heatmap_hides_all(self, qtbot):
        widget = ChessBoardWidget()
        qtbot.addWidget(widget)

        # Enable heatmap first
        white_attacks = [2] * 64
        black_attacks = [0] * 64
        widget.set_heatmap(white_attacks, black_attacks)

        # Now clear
        widget.clear_heatmap()
        for overlay in widget._heatmap_items:
            assert overlay.isVisible() is False
        assert widget._heatmap_visible is False


class TestMainWindowHeatmapToggle:
    def test_heatmap_button_exists(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert hasattr(window._control_panel, 'heatmap_button')
        assert window._control_panel.heatmap_button.isCheckable()

    def test_toggle_heatmap_on_off(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        # Toggle on
        window._control_panel.heatmap_button.setChecked(True)
        window._toggle_heatmap()
        assert window._heatmap_on is True
        assert window._board_widget._heatmap_visible is True

        # Toggle off
        window._control_panel.heatmap_button.setChecked(False)
        window._toggle_heatmap()
        assert window._heatmap_on is False
        assert window._board_widget._heatmap_visible is False
