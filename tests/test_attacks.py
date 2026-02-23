"""Tests for the pure-Python attack map computation."""
import pytest
from duchess.chess_types import Piece
from duchess.attacks import compute_attack_maps


def _empty_board():
    return [Piece.NONE] * 64


def _sq(rank, file):
    return rank * 8 + file


# --- Pawn attacks ---

class TestPawnAttacks:
    def test_white_pawn_attacks_two_squares(self):
        pieces = _empty_board()
        pieces[_sq(1, 4)] = Piece.WHITE_PAWN  # e2
        w, b = compute_attack_maps(pieces)
        # e2 pawn attacks d3 and f3
        assert w[_sq(2, 3)] == 1  # d3
        assert w[_sq(2, 5)] == 1  # f3
        # Does not attack e3 (push, not attack)
        assert w[_sq(2, 4)] == 0

    def test_black_pawn_attacks_downward(self):
        pieces = _empty_board()
        pieces[_sq(6, 4)] = Piece.BLACK_PAWN  # e7
        w, b = compute_attack_maps(pieces)
        # e7 pawn attacks d6 and f6
        assert b[_sq(5, 3)] == 1  # d6
        assert b[_sq(5, 5)] == 1  # f6

    def test_pawn_on_a_file_attacks_one_square(self):
        pieces = _empty_board()
        pieces[_sq(1, 0)] = Piece.WHITE_PAWN  # a2
        w, b = compute_attack_maps(pieces)
        assert w[_sq(2, 1)] == 1   # b3
        assert w[_sq(2, 0)] == 0   # a3 — not diagonal


# --- Knight attacks ---

class TestKnightAttacks:
    def test_knight_center_attacks_eight_squares(self):
        pieces = _empty_board()
        pieces[_sq(3, 3)] = Piece.WHITE_KNIGHT  # d4
        w, b = compute_attack_maps(pieces)
        expected = [
            _sq(1, 2), _sq(1, 4),  # c2, e2
            _sq(2, 1), _sq(2, 5),  # b3, f3
            _sq(4, 1), _sq(4, 5),  # b5, f5
            _sq(5, 2), _sq(5, 4),  # c6, e6
        ]
        for sq in expected:
            assert w[sq] >= 1, f"Knight should attack sq {sq}"
        # Count total attacked squares
        assert sum(1 for x in w if x > 0) == 8

    def test_knight_corner_attacks_two_squares(self):
        pieces = _empty_board()
        pieces[_sq(0, 0)] = Piece.BLACK_KNIGHT  # a1
        w, b = compute_attack_maps(pieces)
        assert b[_sq(1, 2)] == 1  # c2
        assert b[_sq(2, 1)] == 1  # b3
        assert sum(1 for x in b if x > 0) == 2


# --- Sliding pieces ---

class TestSlidingPieces:
    def test_rook_on_empty_board(self):
        pieces = _empty_board()
        pieces[_sq(3, 3)] = Piece.WHITE_ROOK  # d4
        w, b = compute_attack_maps(pieces)
        # d4 rook attacks 14 squares (7 on rank + 7 on file)
        assert sum(1 for x in w if x > 0) == 14

    def test_rook_blocked_by_piece(self):
        pieces = _empty_board()
        pieces[_sq(3, 3)] = Piece.WHITE_ROOK  # d4
        pieces[_sq(3, 5)] = Piece.WHITE_PAWN  # f4 — blocks rook on that ray
        w, b = compute_attack_maps(pieces)
        # Rook attacks f4 (the blocking pawn's square) but NOT g4 or h4
        assert w[_sq(3, 5)] >= 1   # f4 is attacked
        assert w[_sq(3, 6)] == 0   # g4 is NOT attacked
        assert w[_sq(3, 7)] == 0   # h4 is NOT attacked

    def test_bishop_on_empty_board(self):
        pieces = _empty_board()
        pieces[_sq(3, 3)] = Piece.BLACK_BISHOP  # d4
        w, b = compute_attack_maps(pieces)
        # d4 bishop attacks 13 squares
        assert sum(1 for x in b if x > 0) == 13

    def test_queen_attacks_are_bishop_plus_rook(self):
        pieces = _empty_board()
        pieces[_sq(3, 3)] = Piece.WHITE_QUEEN  # d4
        w, _ = compute_attack_maps(pieces)
        # d4 queen attacks 27 squares on empty board
        assert sum(1 for x in w if x > 0) == 27


# --- King ---

class TestKingAttacks:
    def test_king_center_attacks_eight_squares(self):
        pieces = _empty_board()
        pieces[_sq(3, 3)] = Piece.WHITE_KING  # d4
        w, b = compute_attack_maps(pieces)
        assert sum(1 for x in w if x > 0) == 8

    def test_king_corner_attacks_three_squares(self):
        pieces = _empty_board()
        pieces[_sq(0, 0)] = Piece.BLACK_KING  # a1
        w, b = compute_attack_maps(pieces)
        assert sum(1 for x in b if x > 0) == 3


# --- Composite ---

class TestComposite:
    def test_starting_position_attack_counts(self):
        """In the starting position, specific squares should have known attack counts."""
        pieces = _empty_board()
        # Set up starting position
        back_rank_w = [Piece.WHITE_ROOK, Piece.WHITE_KNIGHT, Piece.WHITE_BISHOP, Piece.WHITE_QUEEN,
                       Piece.WHITE_KING, Piece.WHITE_BISHOP, Piece.WHITE_KNIGHT, Piece.WHITE_ROOK]
        back_rank_b = [Piece.BLACK_ROOK, Piece.BLACK_KNIGHT, Piece.BLACK_BISHOP, Piece.BLACK_QUEEN,
                       Piece.BLACK_KING, Piece.BLACK_BISHOP, Piece.BLACK_KNIGHT, Piece.BLACK_ROOK]
        for f in range(8):
            pieces[_sq(0, f)] = back_rank_w[f]
            pieces[_sq(1, f)] = Piece.WHITE_PAWN
            pieces[_sq(6, f)] = Piece.BLACK_PAWN
            pieces[_sq(7, f)] = back_rank_b[f]

        w, b = compute_attack_maps(pieces)

        # e2 pawn is attacked by Ke1, Bf1, Qd1 — at least 3 white pieces defend it
        assert w[_sq(1, 4)] >= 3

        # d3 is attacked by pawns on c2 and e2 — at least 2 white attacks
        assert w[_sq(2, 3)] >= 2

        # Black attacks should mirror white's
        assert b[_sq(5, 3)] >= 2  # d6 attacked by c7 and e7 pawns

    def test_multiple_attackers_stack(self):
        """Two rooks on the same file both attack a square."""
        pieces = _empty_board()
        pieces[_sq(0, 0)] = Piece.WHITE_ROOK  # a1
        pieces[_sq(3, 0)] = Piece.WHITE_ROOK  # a4
        w, b = compute_attack_maps(pieces)
        # a3 is attacked by both rooks (a1 slides up, a4 slides down)
        assert w[_sq(2, 0)] == 2
