# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""DuchessBoard — wraps the UCI engine subprocess with SAN support."""
from duchess.chess_types import Piece, Color, Move
from duchess.engine_wrapper import get_engine

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

# FEN piece char -> Piece enum
_FEN_PIECE_MAP = {
    'P': Piece.WHITE_PAWN, 'N': Piece.WHITE_KNIGHT, 'B': Piece.WHITE_BISHOP,
    'R': Piece.WHITE_ROOK, 'Q': Piece.WHITE_QUEEN, 'K': Piece.WHITE_KING,
    'p': Piece.BLACK_PAWN, 'n': Piece.BLACK_KNIGHT, 'b': Piece.BLACK_BISHOP,
    'r': Piece.BLACK_ROOK, 'q': Piece.BLACK_QUEEN, 'k': Piece.BLACK_KING,
}


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


def _parse_fen_board(fen):
    """Parse a FEN string and return a list of 64 Piece values (index 0 = a1)."""
    parts = fen.split()
    rows = parts[0].split("/")
    board = [Piece.NONE] * 64
    for rank_idx, row in enumerate(rows):
        rank = 7 - rank_idx  # FEN starts from rank 8
        file = 0
        for ch in row:
            if ch.isdigit():
                file += int(ch)
            else:
                sq = rank * 8 + file
                board[sq] = _FEN_PIECE_MAP.get(ch, Piece.NONE)
                file += 1
    return board


def _parse_fen_side(fen):
    """Return 'white' or 'black' from FEN."""
    parts = fen.split()
    return "white" if len(parts) < 2 or parts[1] == "w" else "black"


class InvalidMoveError(Exception):
    pass


class IllegalMoveError(Exception):
    pass


class AmbiguousMoveError(Exception):
    pass


class DuchessBoard:
    """Chess board backed by FEN parsing and UCI engine for move generation/validation."""

    def __init__(self, fen=None):
        self._fen = fen if fen else STARTING_FEN
        self._pieces = _parse_fen_board(self._fen)
        self._side = _parse_fen_side(self._fen)
        self._legal_moves_cache = None
        self._gamestate_cache = None

    def _sync_engine(self):
        """Set the engine's internal position to match our FEN."""
        engine = get_engine()
        engine.set_position_fen(self._fen)

    def _get_legal_move_strings(self):
        """Get legal moves as UCI strings from the engine."""
        if self._legal_moves_cache is None:
            self._sync_engine()
            engine = get_engine()
            self._legal_moves_cache = engine.get_legal_moves()
        return self._legal_moves_cache

    def _invalidate_cache(self):
        self._legal_moves_cache = None
        self._gamestate_cache = None

    @property
    def turn(self):
        return self._side

    @property
    def legal_moves(self):
        """Return list of Move objects for all legal moves."""
        return [Move.from_uci(s) for s in self._get_legal_move_strings()]

    def fen(self):
        return self._fen

    def get_fen(self):
        return self._fen

    def piece_at_sq(self, sq):
        return self._pieces[sq]

    def make_move_uci(self, uci_str):
        """Try to make a UCI move. Returns True if legal, False otherwise."""
        legal = self._get_legal_move_strings()
        if uci_str not in legal:
            return False
        self._apply_move_uci(uci_str)
        return True

    def push(self, move):
        """Push a Move object."""
        self._apply_move_uci(move.to_uci())

    def push_uci(self, uci_str):
        self._apply_move_uci(uci_str)

    def _apply_move_uci(self, uci_str):
        """Apply a move and update the FEN from the engine."""
        self._sync_engine()
        engine = get_engine()
        engine.set_position_fen(self._fen, [uci_str])
        self._fen = engine.get_fen()
        self._pieces = _parse_fen_board(self._fen)
        self._side = _parse_fen_side(self._fen)
        self._invalidate_cache()

    def is_game_over(self):
        return len(self._get_legal_move_strings()) == 0

    def result(self):
        if not self.is_game_over():
            return "*"
        self._sync_engine()
        engine = get_engine()
        state = engine.get_gamestate()
        if state == "checkmate":
            return "0-1" if self._side == "white" else "1-0"
        return "1/2-1/2"

    def is_attacked(self, sq, color):
        """Check if sq is attacked by the given color. color can be Color enum or string."""
        self._sync_engine()
        engine = get_engine()
        if isinstance(color, Color):
            color_str = "white" if color == Color.WHITE else "black"
        else:
            color_str = color
        return engine.is_attacked(sq, color_str)

    def san(self, move):
        """Convert a move to SAN. Must be called BEFORE the move is made."""
        piece = self._pieces[move.from_sq]
        to_name = _sq_name(move.to_sq)
        captured = self._pieces[move.to_sq]

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

        # Check / checkmate suffix — make the move on a copy board
        copy = DuchessBoard(self._fen)
        copy._apply_move_uci(move.to_uci())
        copy_legal = copy._get_legal_move_strings()
        if len(copy_legal) == 0:
            # Could be checkmate or stalemate
            copy._sync_engine()
            engine = get_engine()
            state = engine.get_gamestate()
            if state == "checkmate":
                san_str += "#"
        else:
            king_sq = copy._find_king(copy._side)
            if king_sq is not None:
                attacker = "black" if copy._side == "white" else "white"
                if copy.is_attacked(king_sq, attacker):
                    san_str += "+"

        return san_str

    def _disambiguate(self, move, piece):
        legal = self.legal_moves
        ambiguous = [lm for lm in legal
                     if lm.to_sq == move.to_sq and lm.from_sq != move.from_sq
                     and self._pieces[lm.from_sq] == piece]
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

    def _find_king(self, side):
        king_piece = Piece.WHITE_KING if side == "white" else Piece.BLACK_KING
        for sq in range(64):
            if self._pieces[sq] == king_piece:
                return sq
        return None

    def parse_san(self, san_str):
        """Parse a SAN string and return the matching legal Move."""
        san = san_str.strip()
        legal = self.legal_moves

        # Castling
        if san in ("O-O", "0-0"):
            for m in legal:
                if _is_king(self._pieces[m.from_sq]) and m.to_sq - m.from_sq == 2:
                    return m
            raise IllegalMoveError(f"Castling O-O not legal")
        if san in ("O-O-O", "0-0-0"):
            for m in legal:
                if _is_king(self._pieces[m.from_sq]) and m.from_sq - m.to_sq == 2:
                    return m
            raise IllegalMoveError(f"Castling O-O-O not legal")

        san = san.rstrip("+#")

        # Promotion
        promotion = Piece.NONE
        if "=" in san:
            promo_char = san[-1].lower()
            san = san[:-2]
            if self._side == "white":
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

        piece_map = CHAR_TO_WHITE_PIECE if self._side == "white" else CHAR_TO_BLACK_PIECE
        target_piece = piece_map.get(piece_char)
        if target_piece is None:
            raise InvalidMoveError(f"Unknown piece: {piece_char}")

        candidates = []
        for m in legal:
            if m.to_sq != to_sq:
                continue
            if self._pieces[m.from_sq] != target_piece:
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
                piece = self._pieces[sq]
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
                piece = self._pieces[sq]
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
