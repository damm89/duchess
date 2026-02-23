"""ChessBoardWidget — interactive chess board using QGraphicsView/QGraphicsScene."""
import sys
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QPainterPath, QPolygonF
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsPathItem, QDialog, QVBoxLayout, QPushButton,
)

from duchess.board import DuchessBoard, PIECE_CHARS
from duchess.chess_types import Piece, Color, Move


def _resource_path(relative: str) -> Path:
    """Resolve asset path for both dev and PyInstaller bundles."""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent.parent / relative


ASSETS_DIR = _resource_path("assets/pieces")

LIGHT_SQUARE = QColor("#F0D9B5")
DARK_SQUARE = QColor("#B58863")
HIGHLIGHT_SELECTED = QColor(124, 252, 0, 100)
HIGHLIGHT_LAST = QColor(255, 255, 0, 80)

PIECE_TO_SVG = {
    Piece.WHITE_PAWN: "wP.svg", Piece.WHITE_KNIGHT: "wN.svg", Piece.WHITE_BISHOP: "wB.svg",
    Piece.WHITE_ROOK: "wR.svg", Piece.WHITE_QUEEN: "wQ.svg", Piece.WHITE_KING: "wK.svg",
    Piece.BLACK_PAWN: "bP.svg", Piece.BLACK_KNIGHT: "bN.svg", Piece.BLACK_BISHOP: "bB.svg",
    Piece.BLACK_ROOK: "bR.svg", Piece.BLACK_QUEEN: "bQ.svg", Piece.BLACK_KING: "bK.svg",
}

FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"

SQ_SIZE = 80  # fixed scene square size


def _sq_to_uci(sq):
    return FILE_NAMES[sq % 8] + RANK_NAMES[sq // 8]


def _is_own_piece(piece, turn):
    if piece == Piece.NONE:
        return False
    if turn == "white":
        return piece in (Piece.WHITE_PAWN, Piece.WHITE_KNIGHT, Piece.WHITE_BISHOP,
                         Piece.WHITE_ROOK, Piece.WHITE_QUEEN, Piece.WHITE_KING)
    else:
        return piece in (Piece.BLACK_PAWN, Piece.BLACK_KNIGHT, Piece.BLACK_BISHOP,
                         Piece.BLACK_ROOK, Piece.BLACK_QUEEN, Piece.BLACK_KING)


def _is_pawn(piece):
    return piece in (Piece.WHITE_PAWN, Piece.BLACK_PAWN)


def _sq_to_scene(sq):
    """Convert square index (0=a1) to scene coordinates (top-left of square)."""
    file_idx = sq % 8
    rank_idx = 7 - (sq // 8)  # a1 (sq 0) at bottom -> rank_idx 7
    return QPointF(file_idx * SQ_SIZE, rank_idx * SQ_SIZE)


def _scene_to_sq(pos):
    """Convert scene position to square index, or None if out of bounds."""
    file_idx = int(pos.x() / SQ_SIZE)
    rank_idx = int(pos.y() / SQ_SIZE)
    if file_idx < 0 or file_idx > 7 or rank_idx < 0 or rank_idx > 7:
        return None
    return (7 - rank_idx) * 8 + file_idx


class PromotionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promote to...")
        self.choice = "q"
        layout = QVBoxLayout(self)
        for label, char in [("Queen", "q"), ("Rook", "r"), ("Bishop", "b"), ("Knight", "n")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, c=char: self._choose(c))
            layout.addWidget(btn)

    def _choose(self, char):
        self.choice = char
        self.accept()


class PieceItem(QGraphicsSvgItem):
    """Draggable SVG piece on the board."""

    def __init__(self, svg_path, sq, board_widget):
        super().__init__(svg_path)
        self._sq = sq
        self._board_widget = board_widget
        self._dragging = False
        self._drag_offset = QPointF(0, 0)
        self.setFlag(QGraphicsSvgItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setZValue(1)
        # Scale SVG to fit square with padding
        bounds = self.boundingRect()
        pad = SQ_SIZE * 0.05
        target = SQ_SIZE - 2 * pad
        sx = target / bounds.width() if bounds.width() > 0 else 1
        sy = target / bounds.height() if bounds.height() > 0 else 1
        scale = min(sx, sy)
        self.setScale(scale)
        self._place_at_square(sq)

    def _place_at_square(self, sq):
        """Position piece at the center of the given square."""
        self._sq = sq
        top_left = _sq_to_scene(sq)
        bounds = self.boundingRect()
        scale = self.scale()
        w = bounds.width() * scale
        h = bounds.height() * scale
        self.setPos(top_left.x() + (SQ_SIZE - w) / 2,
                    top_left.y() + (SQ_SIZE - h) / 2)

    def mousePressEvent(self, event):
        try:
            if event.button() != Qt.MouseButton.LeftButton:
                return
            if not self._board_widget.isEnabled():
                return
            piece = self._board_widget.board.piece_at_sq(self._sq)
            if not _is_own_piece(piece, self._board_widget.board.turn):
                # Not our piece — pass to board for click selection logic
                self._board_widget._handle_square_click(self._sq)
                return
            self._dragging = True
            self.setZValue(10)
            self._board_widget._set_selected(self._sq)
            # Store offset from item origin to mouse
            self._drag_offset = event.pos()
            event.accept()
        except Exception as e:
            with open("error_debug.log", "a") as f:
                import traceback
                f.write("mousePressEvent Error:\n")
                traceback.print_exc(file=f)

    def mouseMoveEvent(self, event):
        try:
            if not self._dragging:
                return
            # Move piece to follow cursor
            scene_pos = event.scenePos()
            bounds = self.boundingRect()
            scale = self.scale()
            self.setPos(scene_pos.x() - self._drag_offset.x() * scale,
                        scene_pos.y() - self._drag_offset.y() * scale)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def mouseReleaseEvent(self, event):
        try:
            if not self._dragging:
                return
            self._dragging = False
            self.setZValue(1)
            target_sq = _scene_to_sq(event.scenePos())
            if target_sq is not None and target_sq != self._sq:
                self._board_widget._try_move(self._sq, target_sq)
            else:
                # Snap back
                self._place_at_square(self._sq)
        except Exception as e:
            import traceback
            traceback.print_exc()


class ChessBoardWidget(QGraphicsView):
    move_made = pyqtSignal(str, str)  # (uci, san)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = DuchessBoard()
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, 8 * SQ_SIZE, 8 * SQ_SIZE)
        self.setScene(self._scene)
        self.setMinimumSize(320, 320)
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._square_items = []  # 64 QGraphicsRectItem
        self._piece_items = []   # list of PieceItem currently on scene
        self._arrow_items = []   # PV arrow items
        self._heatmap_items = []  # 64 semi-transparent overlay items
        self._heatmap_visible = False
        self._selected_sq = None
        self._last_move_from = None
        self._last_move_to = None

        self._build_squares()
        self._build_heatmap_overlays()
        self._sync_pieces()

    def _build_squares(self):
        """Create 64 square rect items."""
        for sq in range(64):
            file_idx = sq % 8
            rank_idx = 7 - (sq // 8)
            is_light = (file_idx + (sq // 8)) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            rect = QGraphicsRectItem(file_idx * SQ_SIZE, rank_idx * SQ_SIZE, SQ_SIZE, SQ_SIZE)
            rect.setBrush(QBrush(color))
            rect.setPen(QPen(Qt.PenStyle.NoPen))
            rect.setZValue(0)
            self._scene.addItem(rect)
            self._square_items.append(rect)

    def _build_heatmap_overlays(self):
        """Create 64 invisible overlay items for the threat heatmap."""
        for sq in range(64):
            file_idx = sq % 8
            rank_idx = 7 - (sq // 8)
            rect = QGraphicsRectItem(
                file_idx * SQ_SIZE, rank_idx * SQ_SIZE, SQ_SIZE, SQ_SIZE
            )
            rect.setPen(QPen(Qt.PenStyle.NoPen))
            rect.setBrush(QBrush(QColor(0, 0, 0, 0)))  # fully transparent
            rect.setZValue(0.5)  # above squares, below pieces
            rect.setVisible(False)
            self._scene.addItem(rect)
            self._heatmap_items.append(rect)

    def set_heatmap(self, white_attacks, black_attacks, player_color="white"):
        """Color heatmap overlays based on attack differentials.

        Args:
            white_attacks: list of 64 ints — white attack count per square.
            black_attacks: list of 64 ints — black attack count per square.
            player_color: 'white' or 'black' — determines which side is
                          'friendly' (blue) vs 'hostile' (red).
        """
        self._heatmap_visible = True
        for sq in range(64):
            w = white_attacks[sq]
            b = black_attacks[sq]

            if player_color == "white":
                friendly, hostile = w, b
            else:
                friendly, hostile = b, w

            diff = friendly - hostile
            overlay = self._heatmap_items[sq]

            if diff > 0:
                # Friendly control — blue tint
                alpha = min(120, 30 * diff)
                overlay.setBrush(QBrush(QColor(60, 120, 220, alpha)))
                overlay.setVisible(True)
            elif diff < 0:
                # Hostile control — red tint
                alpha = min(120, 30 * abs(diff))
                overlay.setBrush(QBrush(QColor(220, 60, 60, alpha)))
                overlay.setVisible(True)
            else:
                overlay.setVisible(False)

    def clear_heatmap(self):
        """Hide all heatmap overlays."""
        self._heatmap_visible = False
        for overlay in self._heatmap_items:
            overlay.setVisible(False)

    def _update_square_colors(self):
        """Refresh square highlights."""
        for sq in range(64):
            file_idx = sq % 8
            is_light = (file_idx + (sq // 8)) % 2 == 0
            base = LIGHT_SQUARE if is_light else DARK_SQUARE

            if sq == self._selected_sq:
                # Blend green overlay
                r = (base.red() + HIGHLIGHT_SELECTED.red()) // 2
                g = (base.green() + HIGHLIGHT_SELECTED.green()) // 2
                b = (base.blue() + HIGHLIGHT_SELECTED.blue()) // 2
                color = QColor(r, g, b)
            elif sq == self._last_move_from or sq == self._last_move_to:
                r = (base.red() + HIGHLIGHT_LAST.red()) // 2
                g = (base.green() + HIGHLIGHT_LAST.green()) // 2
                b = (base.blue() + HIGHLIGHT_LAST.blue()) // 2
                color = QColor(r, g, b)
            else:
                color = base

            self._square_items[sq].setBrush(QBrush(color))

    def _sync_pieces(self):
        """Remove old piece items and create new ones matching the board state."""
        for item in self._piece_items:
            self._scene.removeItem(item)
        self._piece_items.clear()

        for sq in range(64):
            piece = self.board.piece_at_sq(sq)
            if piece == Piece.NONE:
                continue
            svg_name = PIECE_TO_SVG.get(piece)
            if svg_name is None:
                continue
            path = ASSETS_DIR / svg_name
            if not path.exists():
                continue
            item = PieceItem(str(path), sq, self)
            self._scene.addItem(item)
            self._piece_items.append(item)

        self._update_square_colors()

    def set_board(self, board):
        self.board = board
        self._selected_sq = None
        self._last_move_from = None
        self._last_move_to = None
        self.clear_arrows()
        self._sync_pieces()

    def set_fen(self, fen_string):
        self.board = DuchessBoard(fen_string)
        self._selected_sq = None
        self._last_move_from = None
        self._last_move_to = None
        self.clear_arrows()
        self._sync_pieces()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # --- Interaction ---

    def mousePressEvent(self, event):
        """Handle clicks on empty squares or for click-click movement."""
        try:
            # Let QGraphicsView dispatch to items first
            super().mousePressEvent(event)
            if event.isAccepted():
                return
            # Click on empty square
            scene_pos = self.mapToScene(event.pos())
            sq = _scene_to_sq(scene_pos)
            if sq is not None:
                self._handle_square_click(sq)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _handle_square_click(self, sq):
        """Handle clicking an empty square or opponent piece (for click-click moves)."""
        piece = self.board.piece_at_sq(sq)

        if self._selected_sq is None:
            # Select own piece
            if _is_own_piece(piece, self.board.turn):
                self._set_selected(sq)
        else:
            if _is_own_piece(piece, self.board.turn) and sq != self._selected_sq:
                # Re-select different own piece
                self._set_selected(sq)
            else:
                # Try to move
                self._try_move(self._selected_sq, sq)

    def _set_selected(self, sq):
        self._selected_sq = sq
        self._update_square_colors()

    def _try_move(self, from_sq, to_sq):
        piece = self.board.piece_at_sq(from_sq)
        uci = _sq_to_uci(from_sq) + _sq_to_uci(to_sq)

        target_rank = to_sq // 8
        if _is_pawn(piece) and (target_rank == 7 or target_rank == 0):
            promo_uci = uci + "q"
            if self._is_legal_uci(promo_uci):
                dialog = PromotionDialog(self)
                dialog.exec()
                uci += dialog.choice
            else:
                self._selected_sq = None
                self._sync_pieces()
                return

        if self._is_legal_uci(uci):
            move = Move.from_uci(uci)
            san = self.board.san(move)
            self._last_move_from = from_sq
            self._last_move_to = to_sq
            self.board.push_uci(uci)
            self._selected_sq = None
            self.clear_arrows()
            self._sync_pieces()
            self.move_made.emit(uci, san)
        else:
            self._selected_sq = None
            self._sync_pieces()

    def _is_legal_uci(self, uci):
        for m in self.board.legal_moves:
            if m.to_uci() == uci:
                return True
        return False

    # --- PV Arrows ---

    def draw_pv_arrows(self, pv_moves):
        """Draw semi-transparent arrows for PV moves. pv_moves is a list of UCI strings."""
        self.clear_arrows()
        for i, uci in enumerate(pv_moves):
            if len(uci) < 4:
                continue
            from_sq = FILE_NAMES.index(uci[0]) + RANK_NAMES.index(uci[1]) * 8
            to_sq = FILE_NAMES.index(uci[2]) + RANK_NAMES.index(uci[3]) * 8
            arrow = self._make_arrow(from_sq, to_sq, i)
            self._scene.addItem(arrow)
            self._arrow_items.append(arrow)

    def _make_arrow(self, from_sq, to_sq, index):
        """Create a QGraphicsPathItem arrow from from_sq to to_sq."""
        start = _sq_to_scene(from_sq) + QPointF(SQ_SIZE / 2, SQ_SIZE / 2)
        end = _sq_to_scene(to_sq) + QPointF(SQ_SIZE / 2, SQ_SIZE / 2)

        # Shorten line slightly so arrowhead is visible
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1:
            length = 1
        ux, uy = dx / length, dy / length

        # Pull end back a bit for arrowhead
        head_len = SQ_SIZE * 0.25
        end_adj = QPointF(end.x() - ux * head_len * 0.5, end.y() - uy * head_len * 0.5)

        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end_adj)

        # Arrowhead
        perp_x, perp_y = -uy, ux
        hw = SQ_SIZE * 0.12  # half-width of arrowhead
        p1 = QPointF(end_adj.x() - ux * head_len + perp_x * hw,
                      end_adj.y() - uy * head_len + perp_y * hw)
        p2 = QPointF(end_adj.x() - ux * head_len - perp_x * hw,
                      end_adj.y() - uy * head_len - perp_y * hw)
        path.moveTo(end_adj)
        path.lineTo(p1)
        path.moveTo(end_adj)
        path.lineTo(p2)

        item = QGraphicsPathItem(path)
        # First arrow is more opaque
        alpha = max(60, 180 - index * 40)
        color = QColor(70, 130, 230, alpha)
        pen = QPen(color, 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        item.setPen(pen)
        item.setZValue(5)
        return item

    def clear_arrows(self):
        for item in self._arrow_items:
            self._scene.removeItem(item)
        self._arrow_items.clear()
