"""DuchessBoard — wraps the C++ duchess_engine.Board with SAN support."""
import duchess_engine
from duchess_engine import Board as _CppBoard, Move as _CppMove, Piece, Color

UNICODE_PIECES = {
    "R": "\u2656", "N": "\u2658", "B": "\u2657", "Q": "\u2655", "K": "\u2654", "P": "\u2659",
    "r": "\u265c", "n": "\u265e", "b": "\u265d", "q": "\u265b", "k": "\u265a", "p": "\u265f",
}

PIECE_CHARS = {
    Piece.WHITE_PAWN: "P", Piece.WHITE_KNIGHT: "N", Piece.WHITE_BISHOP: "B",
    Piece.WHITE_ROOK: "R", Piece.WHITE_QUEEN: "Q", Piece.WHITE_KING: "K",
    Piece.BLACK_PAWN: "p", Piece.BLACK_KNIGHT: "n", Piece.BLACK_BISHOP: "b",
    Piece.BLACK_ROOK: "r", Piece.BLACK_QUEEN: "q", Piece.BLACK_KING: "k",
    Piece.NONE: None,
}

CHAR_TO_WHITE_PIECE = {"P": Piece.WHITE_PAWN, "N": Piece.WHITE_KNIGHT, "B": Piece.WHITE_BISHOP,
                        "R": Piece.WHITE_ROOK, "Q": Piece.WHITE_QUEEN, "K": Piece.WHITE_KING}
CHAR_TO_BLACK_PIECE = {"P": Piece.BLACK_PAWN, "N": Piece.BLACK_KNIGHT, "B": Piece.BLACK_BISHOP,
                        "R": Piece.BLACK_ROOK, "Q": Piece.BLACK_QUEEN, "K": Piece.BLACK_KING}

PROMOTION_CHARS = {"q": Piece.WHITE_QUEEN, "r": Piece.WHITE_ROOK,
                   "b": Piece.WHITE_BISHOP, "n": Piece.WHITE_KNIGHT}
PROMOTION_CHARS_BLACK = {"q": Piece.BLACK_QUEEN, "r": Piece.BLACK_ROOK,
                         "b": Piece.BLACK_BISHOP, "n": Piece.BLACK_KNIGHT}

FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _sq_name(sq):
    return FILE_NAMES[sq % 8] + RANK_NAMES[sq // 8]


def _name_to_sq(name):
    return FILE_NAMES.index(name[0]) + RANK_NAMES.index(name[1]) * 8


def _piece_type_char(piece):
    return PIECE_CHARS.get(piece, None)


def _is_pawn(piece):
    return piece in (Piece.WHITE_PAWN, Piece.BLACK_PAWN)


def _is_king(piece):
    return piece in (Piece.WHITE_KING, Piece.BLACK_KING)


class InvalidMoveError(Exception):
    pass


class IllegalMoveError(Exception):
    pass


class AmbiguousMoveError(Exception):
    pass


class DuchessBoard:
    """Wrapper around the C++ duchess_engine.Board with SAN support."""

    def __init__(self, fen=None):
        if fen is None:
            self._board = _CppBoard()
        else:
            self._board = _CppBoard(fen)

    @property
    def turn(self):
        return "white" if self._board.side_to_move() == Color.WHITE else "black"

    @property
    def legal_moves(self):
        return self._board.generate_legal_moves()

    def fen(self):
        return self._board.to_fen()

    def get_fen(self):
        return self.fen()

    def make_move_uci(self, uci_str):
        """Try to make a UCI move. Returns True if legal, False otherwise."""
        move = _CppMove.from_uci(uci_str)
        legal = self._board.generate_legal_moves()
        for lm in legal:
            if lm.from_sq == move.from_sq and lm.to_sq == move.to_sq and lm.promotion == move.promotion:
                self._board.make_move(lm)
                return True
        return False

    def push(self, move):
        self._board.make_move(move)

    def push_uci(self, uci_str):
        move = _CppMove.from_uci(uci_str)
        self._board.make_move(move)

    def piece_at_sq(self, sq):
        return self._board.piece_at_sq(sq)

    def is_game_over(self):
        return len(self._board.generate_legal_moves()) == 0

    def result(self):
        if not self.is_game_over():
            return "*"
        if duchess_engine.is_checkmate(self._board):
            if self._board.side_to_move() == Color.WHITE:
                return "0-1"
            else:
                return "1-0"
        return "1/2-1/2"

    def is_attacked(self, sq, color):
        return self._board.is_attacked(sq, color)

    def san(self, move):
        """Convert a move to SAN. Must be called BEFORE the move is made."""
        piece = self._board.piece_at_sq(move.from_sq)
        to_name = _sq_name(move.to_sq)
        captured = self._board.piece_at_sq(move.to_sq)

        # Castling
        if _is_king(piece) and abs(move.from_sq - move.to_sq) == 2:
            san_str = "O-O" if move.to_sq > move.from_sq else "O-O-O"
        elif _is_pawn(piece):
            is_capture = captured != Piece.NONE
            # En passant: file changes but no piece on target
            if not is_capture and (move.from_sq % 8) != (move.to_sq % 8):
                is_capture = True
            if is_capture:
                san_str = FILE_NAMES[move.from_sq % 8] + "x" + to_name
            else:
                san_str = to_name
            if move.promotion != Piece.NONE:
                promo_char = _piece_type_char(move.promotion)
                if promo_char:
                    san_str += "=" + promo_char.upper()
        else:
            char = _piece_type_char(piece).upper()
            is_capture = captured != Piece.NONE
            disambig = "" if char == "K" else self._disambiguate(move, piece)
            if is_capture:
                san_str = char + disambig + "x" + to_name
            else:
                san_str = char + disambig + to_name

        # Check / checkmate suffix
        copy = _CppBoard(self._board.to_fen())
        copy.make_move(move)
        copy_legal = copy.generate_legal_moves()
        if len(copy_legal) == 0 and duchess_engine.is_checkmate(copy):
            san_str += "#"
        else:
            king_sq = self._find_king(copy, copy.side_to_move())
            if king_sq is not None:
                attacker_color = Color.BLACK if copy.side_to_move() == Color.WHITE else Color.WHITE
                if copy.is_attacked(king_sq, attacker_color):
                    san_str += "+"

        return san_str

    def _disambiguate(self, move, piece):
        legal = self._board.generate_legal_moves()
        ambiguous = [lm for lm in legal
                     if lm.to_sq == move.to_sq and lm.from_sq != move.from_sq
                     and self._board.piece_at_sq(lm.from_sq) == piece]
        if not ambiguous:
            return ""
        from_file = move.from_sq % 8
        from_rank = move.from_sq // 8
        same_file = any(m.from_sq % 8 == from_file for m in ambiguous)
        same_rank = any(m.from_sq // 8 == from_rank for m in ambiguous)
        if not same_file:
            return FILE_NAMES[from_file]
        if not same_rank:
            return RANK_NAMES[from_rank]
        return FILE_NAMES[from_file] + RANK_NAMES[from_rank]

    def _find_king(self, board, color):
        king_piece = Piece.WHITE_KING if color == Color.WHITE else Piece.BLACK_KING
        for sq in range(64):
            if board.piece_at_sq(sq) == king_piece:
                return sq
        return None

    def parse_san(self, san_str):
        """Parse a SAN string and return the matching legal move."""
        san = san_str.strip()
        legal = self._board.generate_legal_moves()

        # Castling
        if san in ("O-O", "0-0"):
            for m in legal:
                if _is_king(self._board.piece_at_sq(m.from_sq)) and m.to_sq - m.from_sq == 2:
                    return m
            raise IllegalMoveError(f"Castling O-O not legal")
        if san in ("O-O-O", "0-0-0"):
            for m in legal:
                if _is_king(self._board.piece_at_sq(m.from_sq)) and m.from_sq - m.to_sq == 2:
                    return m
            raise IllegalMoveError(f"Castling O-O-O not legal")

        san = san.rstrip("+#")

        # Promotion
        promotion = Piece.NONE
        if "=" in san:
            promo_char = san[-1].lower()
            san = san[:-2]
            if self._board.side_to_move() == Color.WHITE:
                promotion = PROMOTION_CHARS.get(promo_char, Piece.NONE)
            else:
                promotion = PROMOTION_CHARS_BLACK.get(promo_char, Piece.NONE)

        # Piece type
        if san[0] in "NBRQK":
            piece_char = san[0]
            san = san[1:]
        else:
            piece_char = "P"

        san = san.replace("x", "")

        if len(san) < 2:
            raise InvalidMoveError(f"Cannot parse SAN: {san_str}")
        to_name = san[-2:]
        disambig = san[:-2]
        if to_name[0] not in FILE_NAMES or to_name[1] not in RANK_NAMES:
            raise InvalidMoveError(f"Cannot parse SAN: {san_str}")
        to_sq = _name_to_sq(to_name)

        piece_map = CHAR_TO_WHITE_PIECE if self._board.side_to_move() == Color.WHITE else CHAR_TO_BLACK_PIECE
        target_piece = piece_map.get(piece_char)
        if target_piece is None:
            raise InvalidMoveError(f"Unknown piece: {piece_char}")

        candidates = []
        for m in legal:
            if m.to_sq != to_sq:
                continue
            if self._board.piece_at_sq(m.from_sq) != target_piece:
                continue
            if promotion != Piece.NONE and m.promotion != promotion:
                continue
            candidates.append(m)

        if disambig:
            filtered = []
            for m in candidates:
                from_file = FILE_NAMES[m.from_sq % 8]
                from_rank = RANK_NAMES[m.from_sq // 8]
                if len(disambig) == 1:
                    if disambig in FILE_NAMES and from_file == disambig:
                        filtered.append(m)
                    elif disambig in RANK_NAMES and from_rank == disambig:
                        filtered.append(m)
                elif len(disambig) == 2:
                    if from_file == disambig[0] and from_rank == disambig[1]:
                        filtered.append(m)
            candidates = filtered

        if len(candidates) == 0:
            raise IllegalMoveError(f"No legal move matches: {san_str}")
        if len(candidates) == 1:
            return candidates[0]

        # Multiple: filter out promotions if none specified
        if promotion == Piece.NONE:
            non_promo = [m for m in candidates if m.promotion == Piece.NONE]
            if len(non_promo) == 1:
                return non_promo[0]

        raise AmbiguousMoveError(f"Ambiguous move: {san_str}")

    def to_html(self):
        light_bg = "#F0D9B5"
        dark_bg = "#B58863"
        html = '<table style="border-collapse:collapse;border:2px solid #333;font-size:0;">'
        for rank in range(7, -1, -1):
            html += "<tr>"
            html += (
                f'<td style="width:20px;text-align:center;vertical-align:middle;'
                f'font-size:13px;color:#666;padding:0 4px 0 0;">{rank + 1}</td>'
            )
            for file in range(8):
                sq = rank * 8 + file
                piece = self._board.piece_at_sq(sq)
                is_light = (rank + file) % 2 == 1
                bg = light_bg if is_light else dark_bg
                char = PIECE_CHARS.get(piece)
                sym = UNICODE_PIECES.get(char, "") if char else ""
                if char and char.islower():
                    color = "#000"
                elif char:
                    color = "#fff"
                else:
                    color = "#000"
                html += (
                    f'<td style="width:40px;height:40px;text-align:center;'
                    f'vertical-align:middle;background:{bg};font-size:28px;'
                    f'color:{color};padding:0;">{sym}</td>'
                )
            html += "</tr>"
        html += '<tr><td></td>'
        for f in "abcdefgh":
            html += (
                f'<td style="text-align:center;font-size:13px;color:#666;'
                f'padding:2px 0 0 0;">{f}</td>'
            )
        html += "</tr></table>"
        return html

    def pretty(self):
        lines = []
        lines.append("  +-----------------+")
        for rank in range(7, -1, -1):
            row = f"{rank + 1} |"
            for file in range(8):
                sq = rank * 8 + file
                piece = self._board.piece_at_sq(sq)
                char = PIECE_CHARS.get(piece)
                if char:
                    row += f" {UNICODE_PIECES[char]}"
                else:
                    row += " ."
            row += " |"
            lines.append(row)
        lines.append("  +-----------------+")
        lines.append("    a b c d e f g h")
        return "\n".join(lines)

    def __str__(self):
        return self.pretty()
