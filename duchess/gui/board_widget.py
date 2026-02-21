"""ChessBoardWidget — interactive chess board using DuchessBoard + PyQt6."""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget, QDialog, QVBoxLayout, QPushButton

from duchess.board import DuchessBoard, PIECE_CHARS
from duchess_engine import Piece, Color


def _resource_path(relative: str) -> Path:
    """Resolve asset path for both dev and PyInstaller bundles."""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent.parent / relative


ASSETS_DIR = _resource_path("assets/pieces")

LIGHT_SQUARE = QColor("#F0D9B5")
DARK_SQUARE = QColor("#B58863")
HIGHLIGHT_SELECTED = QColor(124, 252, 0, 100)   # green overlay for selected square
HIGHLIGHT_LAST_FROM = QColor(255, 255, 0, 80)    # yellow overlay for last move
HIGHLIGHT_LAST_TO = QColor(255, 255, 0, 80)

# Map Piece enum to SVG filenames
PIECE_TO_SVG = {
    Piece.WHITE_PAWN: "wP.svg", Piece.WHITE_KNIGHT: "wN.svg", Piece.WHITE_BISHOP: "wB.svg",
    Piece.WHITE_ROOK: "wR.svg", Piece.WHITE_QUEEN: "wQ.svg", Piece.WHITE_KING: "wK.svg",
    Piece.BLACK_PAWN: "bP.svg", Piece.BLACK_KNIGHT: "bN.svg", Piece.BLACK_BISHOP: "bB.svg",
    Piece.BLACK_ROOK: "bR.svg", Piece.BLACK_QUEEN: "bQ.svg", Piece.BLACK_KING: "bK.svg",
}

FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"


def _sq_to_uci(sq):
    return FILE_NAMES[sq % 8] + RANK_NAMES[sq // 8]


def _is_own_piece(piece, turn):
    """Check if piece belongs to the side to move."""
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


class PromotionDialog(QDialog):
    """Simple dialog for choosing promotion piece."""

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


class ChessBoardWidget(QWidget):
    move_made = pyqtSignal(str, str)  # (uci, san)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = DuchessBoard()
        self._renderers = {}
        self._selected_sq = None       # square index (0-63) or None
        self._last_move_from = None    # square index of last move origin
        self._last_move_to = None      # square index of last move destination
        self._load_pieces()
        self.setMinimumSize(320, 320)

    def _load_pieces(self):
        for piece, filename in PIECE_TO_SVG.items():
            path = ASSETS_DIR / filename
            if path.exists():
                renderer = QSvgRenderer(str(path))
                if renderer.isValid():
                    self._renderers[piece] = renderer

    def set_board(self, board):
        """Set a DuchessBoard instance and repaint."""
        self.board = board
        self._selected_sq = None
        self._last_move_from = None
        self._last_move_to = None
        self.update()

    def set_fen(self, fen_string):
        """Set position from FEN string."""
        self.board = DuchessBoard(fen_string)
        self._selected_sq = None
        self._last_move_from = None
        self._last_move_to = None
        self.update()

    # --- Coordinate helpers ---

    def _board_geometry(self):
        """Return (sq_size, x_offset, y_offset)."""
        board_size = min(self.width(), self.height())
        sq_size = board_size / 8
        x_off = (self.width() - board_size) / 2
        y_off = (self.height() - board_size) / 2
        return sq_size, x_off, y_off

    def _pixel_to_square(self, x, y):
        """Convert pixel coords to square index (0=a1), or None if outside board."""
        sq_size, x_off, y_off = self._board_geometry()
        file_idx = int((x - x_off) / sq_size)
        rank_idx = int((y - y_off) / sq_size)  # 0 = rank 8 (top)
        if file_idx < 0 or file_idx > 7 or rank_idx < 0 or rank_idx > 7:
            return None
        # Convert: rank_idx 0 = rank 8, so square rank = 7 - rank_idx
        sq = (7 - rank_idx) * 8 + file_idx
        return sq

    # --- Paint ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sq_size, x_off, y_off = self._board_geometry()

        for sq in range(64):
            file_idx = sq % 8
            rank_idx = 7 - (sq // 8)  # sq 0 (a1) -> rank_idx 7 (bottom)

            # Draw square
            is_light = (file_idx + (sq // 8)) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            rect = QRectF(x_off + file_idx * sq_size, y_off + rank_idx * sq_size, sq_size, sq_size)
            painter.fillRect(rect, color)

            # Highlight last move
            if sq == self._last_move_from or sq == self._last_move_to:
                painter.fillRect(rect, HIGHLIGHT_LAST_FROM)

            # Highlight selected square
            if sq == self._selected_sq:
                painter.fillRect(rect, HIGHLIGHT_SELECTED)

            # Draw piece
            piece = self.board.piece_at_sq(sq)
            renderer = self._renderers.get(piece)
            if renderer:
                padding = sq_size * 0.05
                piece_rect = QRectF(
                    x_off + file_idx * sq_size + padding,
                    y_off + rank_idx * sq_size + padding,
                    sq_size - 2 * padding,
                    sq_size - 2 * padding,
                )
                renderer.render(painter, piece_rect)

        painter.end()

    # --- Mouse events ---

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        sq = self._pixel_to_square(event.position().x(), event.position().y())
        if sq is None:
            self._selected_sq = None
            self.update()
            return

        piece = self.board.piece_at_sq(sq)

        if self._selected_sq is None:
            # First click: select if it's our piece
            if _is_own_piece(piece, self.board.turn):
                self._selected_sq = sq
                self.update()
        else:
            # Second click on own piece: reselect
            if _is_own_piece(piece, self.board.turn) and sq != self._selected_sq:
                self._selected_sq = sq
                self.update()
            else:
                # Try to move
                self._try_move(self._selected_sq, sq)

    def mouseReleaseEvent(self, event):
        # Drag support: if released on a different square than selected, try move
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._selected_sq is None:
            return
        sq = self._pixel_to_square(event.position().x(), event.position().y())
        if sq is not None and sq != self._selected_sq:
            self._try_move(self._selected_sq, sq)

    def _try_move(self, from_sq, to_sq):
        """Attempt to make a move. Handles promotion if needed."""
        piece = self.board.piece_at_sq(from_sq)
        uci = _sq_to_uci(from_sq) + _sq_to_uci(to_sq)

        # Check for pawn promotion
        target_rank = to_sq // 8
        if _is_pawn(piece) and (target_rank == 7 or target_rank == 0):
            # Verify this is actually a legal promotion move before showing dialog
            promo_uci = uci + "q"
            if self._is_legal_uci(promo_uci):
                dialog = PromotionDialog(self)
                dialog.exec()
                uci += dialog.choice
            else:
                self._selected_sq = None
                self.update()
                return

        if self._is_legal_uci(uci):
            # Compute SAN before pushing (san() requires pre-move state)
            from duchess_engine import Move as _CppMove
            move = _CppMove.from_uci(uci)
            san = self.board.san(move)
            self._last_move_from = from_sq
            self._last_move_to = to_sq
            self.board.push_uci(uci)
            self._selected_sq = None
            self.update()
            self.move_made.emit(uci, san)
        else:
            self._selected_sq = None
            self.update()

    def _is_legal_uci(self, uci):
        """Check if a UCI string matches a legal move."""
        legal = self.board.legal_moves
        for m in legal:
            if m.to_uci() == uci:
                return True
        return False
