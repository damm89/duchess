# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""EvaluationBar — vertical bar showing engine evaluation."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget


class EvaluationBar(QWidget):
    """Vertical bar that fills proportionally based on engine score."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(28)
        self._score_cp = 0      # centipawns from white's perspective
        self._mate = None       # positive = white mates, negative = black mates
        self._depth = 0

    def set_score(self, cp=0, mate=None, depth=0):
        self._score_cp = cp
        self._mate = mate
        self._depth = depth
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Calculate white's fill fraction (0.0 = black winning, 1.0 = white winning)
        if self._mate is not None:
            white_frac = 1.0 if self._mate > 0 else 0.0
        else:
            # Sigmoid-ish mapping: clamp at +/- 1000 cp
            clamped = max(-1000, min(1000, self._score_cp))
            white_frac = 0.5 + clamped / 2000.0

        # Draw black portion (top)
        black_h = h * (1.0 - white_frac)
        painter.fillRect(QRectF(0, 0, w, black_h), QColor(50, 50, 50))

        # Draw white portion (bottom)
        painter.fillRect(QRectF(0, black_h, w, h - black_h), QColor(240, 240, 240))

        # Draw score text
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        if self._mate is not None:
            text = f"M{abs(self._mate)}"
        else:
            text = f"{self._score_cp / 100:+.1f}"

        # Draw text near the dividing line
        text_y = black_h
        if white_frac > 0.5:
            # White is winning — draw in the black region near divider
            painter.setPen(QColor(220, 220, 220))
            text_y = max(14, black_h - 4)
        else:
            # Black is winning — draw in the white region near divider
            painter.setPen(QColor(40, 40, 40))
            text_y = min(h - 4, black_h + 14)

        painter.drawText(QRectF(0, text_y - 14, w, 16), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
