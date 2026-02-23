"""Pure-Python attack map computation for threat heatmaps.

Computes, for every square on the board, how many white and black pieces
attack it.  This avoids 128 subprocess calls to the C++ engine per position.
"""
from duchess.chess_types import Piece

# Pre-computed knight offsets (row_delta, col_delta)
_KNIGHT_OFFSETS = [
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
]

# Pre-computed king offsets
_KING_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]

# Sliding directions
_BISHOP_DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_ROOK_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_QUEEN_DIRS = _BISHOP_DIRS + _ROOK_DIRS

# Piece classification helpers
_WHITE_PIECES = frozenset({
    Piece.WHITE_PAWN, Piece.WHITE_KNIGHT, Piece.WHITE_BISHOP,
    Piece.WHITE_ROOK, Piece.WHITE_QUEEN, Piece.WHITE_KING,
})
_BLACK_PIECES = frozenset({
    Piece.BLACK_PAWN, Piece.BLACK_KNIGHT, Piece.BLACK_BISHOP,
    Piece.BLACK_ROOK, Piece.BLACK_QUEEN, Piece.BLACK_KING,
})


def _sq(rank, file):
    return rank * 8 + file


def _in_bounds(r, f):
    return 0 <= r <= 7 and 0 <= f <= 7


def compute_attack_maps(pieces):
    """Compute attack counts for every square.

    Args:
        pieces: list of 64 Piece values (index 0 = a1, index 63 = h8).

    Returns:
        (white_attacks, black_attacks): two lists of 64 ints.
        white_attacks[sq] = number of white pieces that attack sq.
        black_attacks[sq] = number of black pieces that attack sq.
    """
    white_attacks = [0] * 64
    black_attacks = [0] * 64

    for sq in range(64):
        piece = pieces[sq]
        if piece == Piece.NONE:
            continue

        rank = sq // 8
        file = sq % 8
        is_white = piece in _WHITE_PIECES
        target = white_attacks if is_white else black_attacks

        if piece in (Piece.WHITE_PAWN, Piece.BLACK_PAWN):
            _add_pawn_attacks(rank, file, is_white, target)
        elif piece in (Piece.WHITE_KNIGHT, Piece.BLACK_KNIGHT):
            _add_jump_attacks(rank, file, _KNIGHT_OFFSETS, target)
        elif piece in (Piece.WHITE_BISHOP, Piece.BLACK_BISHOP):
            _add_sliding_attacks(rank, file, _BISHOP_DIRS, pieces, target)
        elif piece in (Piece.WHITE_ROOK, Piece.BLACK_ROOK):
            _add_sliding_attacks(rank, file, _ROOK_DIRS, pieces, target)
        elif piece in (Piece.WHITE_QUEEN, Piece.BLACK_QUEEN):
            _add_sliding_attacks(rank, file, _QUEEN_DIRS, pieces, target)
        elif piece in (Piece.WHITE_KING, Piece.BLACK_KING):
            _add_jump_attacks(rank, file, _KING_OFFSETS, target)

    return white_attacks, black_attacks


def _add_pawn_attacks(rank, file, is_white, target):
    """Add pawn attack squares (diagonal captures only, not pushes)."""
    dr = 1 if is_white else -1
    for df in (-1, 1):
        r2, f2 = rank + dr, file + df
        if _in_bounds(r2, f2):
            target[_sq(r2, f2)] += 1


def _add_jump_attacks(rank, file, offsets, target):
    """Add attacks for non-sliding pieces (knight, king)."""
    for dr, df in offsets:
        r2, f2 = rank + dr, file + df
        if _in_bounds(r2, f2):
            target[_sq(r2, f2)] += 1


def _add_sliding_attacks(rank, file, directions, pieces, target):
    """Add attacks for sliding pieces (bishop, rook, queen).

    Rays stop at the first piece encountered (but that square IS attacked).
    """
    for dr, df in directions:
        r, f = rank + dr, file + df
        while _in_bounds(r, f):
            sq = _sq(r, f)
            target[sq] += 1
            if pieces[sq] != Piece.NONE:
                break  # blocked by a piece
            r += dr
            f += df
