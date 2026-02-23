# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""OpeningExplorerWidget — shows opening statistics from the Lichess Masters database.

Data is sourced from the Lichess Opening Explorer API.
Lichess (https://lichess.org) is a free, open-source chess server.
See duchess/lichess_api.py for full attribution.
"""
import logging
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt6.QtGui import QColor, QPainter, QFont
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QStyledItemDelegate, QAbstractItemView,
)

from duchess.lichess_api import LichessExplorerClient

logger = logging.getLogger(__name__)


class _QueryWorker(QThread):
    """Background thread to query the Lichess API without blocking the GUI."""
    finished = pyqtSignal(dict)  # emits the parsed result

    def __init__(self, client: LichessExplorerClient, fen: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._fen = fen
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        result = self._client.query(self._fen)
        if not self._cancelled:
            self.finished.emit(result)


class WDLBarDelegate(QStyledItemDelegate):
    """Paints a horizontal Win/Draw/Loss bar in a table cell.

    The item data (Qt.ItemDataRole.UserRole) should be a tuple:
        (win_pct: float, draw_pct: float, loss_pct: float)
    """

    _WHITE_WIN = QColor(100, 180, 80)     # green
    _DRAW = QColor(180, 180, 180)         # gray
    _BLACK_WIN = QColor(200, 70, 70)      # red
    _TEXT_COLOR = QColor(30, 30, 30)

    def paint(self, painter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, (list, tuple)) or len(data) < 3:
            super().paint(painter, option, index)
            return

        win_pct, draw_pct, loss_pct = data
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect.adjusted(2, 3, -2, -3)
        w = rect.width()
        h = rect.height()
        x = rect.x()
        y = rect.y()

        # Draw bar segments
        w_win = w * win_pct / 100.0
        w_draw = w * draw_pct / 100.0
        w_loss = w * loss_pct / 100.0

        painter.fillRect(QRectF(x, y, w_win, h), self._WHITE_WIN)
        painter.fillRect(QRectF(x + w_win, y, w_draw, h), self._DRAW)
        painter.fillRect(QRectF(x + w_win + w_draw, y, w_loss, h), self._BLACK_WIN)

        # Draw percentage text centered
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(self._TEXT_COLOR)

        text = f"{win_pct:.0f}/{draw_pct:.0f}/{loss_pct:.0f}"
        painter.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setWidth(max(hint.width(), 120))
        return hint


class OpeningExplorerWidget(QGroupBox):
    """Panel showing opening move statistics from the Lichess Masters database.

    Credits: Data provided by the Lichess Opening Explorer
    (https://lichess.org/api#tag/Opening-Explorer).
    """

    move_clicked = pyqtSignal(str)  # emits UCI string when user double-clicks a row

    # Column indices
    COL_MOVE = 0
    COL_GAMES = 1
    COL_SCORE = 2
    COL_RATING = 3
    COL_OPENING = 4

    def __init__(self, parent=None):
        super().__init__("Opening Explorer", parent)
        self._client = LichessExplorerClient()
        self._worker = None
        self._current_moves = []  # list of move dicts from last query

        layout = QVBoxLayout(self)

        # Opening name label
        self._opening_label = QLabel("Lichess Masters Database")
        self._opening_label.setStyleSheet(
            "font-weight: bold; color: #666; padding: 2px;"
        )
        layout.addWidget(self._opening_label)

        # Status / credit label
        self._status_label = QLabel(
            '<span style="color:#999; font-size:9px;">'
            'Data: <a href="https://lichess.org" style="color:#999;">lichess.org</a> '
            'Masters Explorer</span>'
        )
        self._status_label.setOpenExternalLinks(True)
        layout.addWidget(self._status_label)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Move", "Games", "Score", "Rating", "Opening"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COL_MOVE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_GAMES, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_SCORE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_RATING, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_OPENING, QHeaderView.ResizeMode.Stretch)

        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(150)

        # Custom delegate for the Score column
        self._wdl_delegate = WDLBarDelegate(self._table)
        self._table.setItemDelegateForColumn(self.COL_SCORE, self._wdl_delegate)

        # Double-click to play a move
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        layout.addWidget(self._table)

    def update_position(self, fen: str):
        """Query the Lichess API for the given FEN (runs on background thread)."""
        # Cancel any in-flight query
        if self._worker is not None:
            self._worker.cancel()
            if self._worker.isRunning():
                self._worker.wait(500)
            self._worker = None

        self._status_label.setText(
            '<span style="color:#999; font-size:9px;">Loading...</span>'
        )

        self._worker = _QueryWorker(self._client, fen, parent=self)
        self._worker.finished.connect(self._on_results)
        self._worker.start()

    def _on_results(self, result: dict):
        """Populate the table with query results."""
        self._current_moves = result.get("moves", [])
        total = result.get("total", 0)

        # Update opening label
        opening = result.get("opening")
        if opening:
            self._opening_label.setText(opening)
        elif total > 0:
            self._opening_label.setText("Starting Position")
        else:
            self._opening_label.setText("Position not in database")

        # Update status
        if total > 0:
            self._status_label.setText(
                f'<span style="color:#999; font-size:9px;">'
                f'{total:,} master games · '
                f'<a href="https://lichess.org" style="color:#999;">lichess.org</a>'
                f'</span>'
            )
        else:
            self._status_label.setText(
                '<span style="color:#999; font-size:9px;">'
                'No data · <a href="https://lichess.org" style="color:#999;">lichess.org</a>'
                '</span>'
            )

        # Populate table
        moves = self._current_moves
        self._table.setRowCount(len(moves))

        for row, m in enumerate(moves):
            # Move (SAN) — bold
            move_item = QTableWidgetItem(m["san"])
            move_font = move_item.font()
            move_font.setBold(True)
            move_item.setFont(move_font)
            self._table.setItem(row, self.COL_MOVE, move_item)

            # Games count
            games_item = QTableWidgetItem(f'{m["total"]:,}')
            games_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, self.COL_GAMES, games_item)

            # Score (WDL bar) — store percentages in UserRole
            score_item = QTableWidgetItem()
            score_item.setData(
                Qt.ItemDataRole.UserRole,
                (m["win_pct"], m["draw_pct"], m["loss_pct"]),
            )
            self._table.setItem(row, self.COL_SCORE, score_item)

            # Average rating
            rating_item = QTableWidgetItem(str(m["avg_rating"]))
            rating_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self._table.setItem(row, self.COL_RATING, rating_item)

            # Opening name
            opening_text = m.get("opening_name", "")
            if m.get("opening_eco"):
                opening_text = f'{m["opening_eco"]} {opening_text}'.strip()
            opening_item = QTableWidgetItem(opening_text)
            opening_item.setToolTip(opening_text)
            self._table.setItem(row, self.COL_OPENING, opening_item)

        self._table.resizeRowsToContents()

    def _on_cell_double_clicked(self, row, col):
        """Emit move_clicked signal with the UCI string of the clicked move."""
        if 0 <= row < len(self._current_moves):
            uci = self._current_moves[row]["uci"]
            if uci:
                self.move_clicked.emit(uci)
