"""Pure-Python chess types matching the C++ engine's Piece/Color enums and Move struct."""
from enum import IntEnum


class Piece(IntEnum):
    NONE = 0
    WHITE_PAWN = 1
    WHITE_KNIGHT = 2
    WHITE_BISHOP = 3
    WHITE_ROOK = 4
    WHITE_QUEEN = 5
    WHITE_KING = 6
    BLACK_PAWN = 7
    BLACK_KNIGHT = 8
    BLACK_BISHOP = 9
    BLACK_ROOK = 10
    BLACK_QUEEN = 11
    BLACK_KING = 12


class Color(IntEnum):
    WHITE = 0
    BLACK = 1


FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"


class Move:
    """Lightweight move representation matching the C++ Move struct."""

    __slots__ = ("from_sq", "to_sq", "promotion")

    def __init__(self, from_sq=0, to_sq=0, promotion=Piece.NONE):
        self.from_sq = from_sq
        self.to_sq = to_sq
        self.promotion = promotion

    def to_uci(self):
        uci = FILE_NAMES[self.from_sq % 8] + RANK_NAMES[self.from_sq // 8]
        uci += FILE_NAMES[self.to_sq % 8] + RANK_NAMES[self.to_sq // 8]
        if self.promotion != Piece.NONE:
            promo_map = {
                Piece.WHITE_QUEEN: "q", Piece.BLACK_QUEEN: "q",
                Piece.WHITE_ROOK: "r", Piece.BLACK_ROOK: "r",
                Piece.WHITE_BISHOP: "b", Piece.BLACK_BISHOP: "b",
                Piece.WHITE_KNIGHT: "n", Piece.BLACK_KNIGHT: "n",
            }
            uci += promo_map.get(self.promotion, "q")
        return uci

    @staticmethod
    def from_uci(uci_str):
        s = uci_str.strip()
        from_sq = FILE_NAMES.index(s[0]) + RANK_NAMES.index(s[1]) * 8
        to_sq = FILE_NAMES.index(s[2]) + RANK_NAMES.index(s[3]) * 8
        promotion = Piece.NONE
        if len(s) == 5:
            to_rank = to_sq // 8
            is_white = to_rank == 7
            promo_char = s[4].lower()
            if is_white:
                promo_map = {"q": Piece.WHITE_QUEEN, "r": Piece.WHITE_ROOK,
                             "b": Piece.WHITE_BISHOP, "n": Piece.WHITE_KNIGHT}
            else:
                promo_map = {"q": Piece.BLACK_QUEEN, "r": Piece.BLACK_ROOK,
                             "b": Piece.BLACK_BISHOP, "n": Piece.BLACK_KNIGHT}
            promotion = promo_map.get(promo_char, Piece.NONE)
        return Move(from_sq, to_sq, promotion)

    def __repr__(self):
        return f"Move('{self.to_uci()}')"

    def __eq__(self, other):
        if not isinstance(other, Move):
            return NotImplemented
        return (self.from_sq == other.from_sq and self.to_sq == other.to_sq
                and self.promotion == other.promotion)

    def __hash__(self):
        return hash((self.from_sq, self.to_sq, self.promotion))
