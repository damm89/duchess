"""Phase 2 Step 2.2 — API verification: FEN, legal moves, search, checkmate/stalemate."""
import pytest


def test_board_fen_round_trip():
    """Board created from FEN should produce the same FEN back."""
    from duchess_engine import Board

    fens = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "r1bqkb1r/pppppppp/2n2n2/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        "8/8/4k3/8/8/4K3/8/8 w - - 0 1",
    ]
    for fen in fens:
        b = Board(fen)
        assert b.to_fen() == fen, f"FEN round-trip failed for: {fen}"


def test_starting_position_legal_moves():
    """Starting position should have exactly 20 legal moves."""
    from duchess_engine import Board

    b = Board()
    moves = b.generate_legal_moves()
    assert len(moves) == 20


def test_legal_moves_uci_format():
    """Legal moves should convert to valid UCI strings."""
    from duchess_engine import Board

    b = Board()
    moves = b.generate_legal_moves()
    uci_moves = [m.to_uci() for m in moves]
    # All UCI strings should be 4 or 5 chars (5 for promotion)
    for uci in uci_moves:
        assert len(uci) in (4, 5), f"Invalid UCI length: {uci}"
    # e2e4 should be in the starting moves
    assert "e2e4" in uci_moves


def test_make_move():
    """Making a move should change the board state."""
    from duchess_engine import Board, Move

    b = Board()
    m = Move.from_uci("e2e4")
    b.make_move(m)
    assert b.to_fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def test_side_to_move():
    """side_to_move should alternate after moves."""
    from duchess_engine import Board, Move, Color

    b = Board()
    assert b.side_to_move() == Color.WHITE
    b.make_move(Move.from_uci("e2e4"))
    assert b.side_to_move() == Color.BLACK


def test_piece_at_sq():
    """piece_at_sq should return correct pieces."""
    from duchess_engine import Board, Piece

    b = Board()
    # e2 = square 12 (row 1, col 4)
    assert b.piece_at_sq(12) == Piece.WHITE_PAWN
    # e1 = square 4 (row 0, col 4)
    assert b.piece_at_sq(4) == Piece.WHITE_KING
    # e8 = square 60 (row 7, col 4)
    assert b.piece_at_sq(60) == Piece.BLACK_KING
    # e4 = square 28 — empty
    assert b.piece_at_sq(28) == Piece.NONE


def test_search_best_move():
    """Search should return a valid best move."""
    from duchess_engine import Board, search

    b = Board()
    result = search(b, 3)
    uci = result.best_move.to_uci()
    assert len(uci) in (4, 5)
    assert result.nodes > 0


def test_search_captures_free_piece():
    """Search should find a free piece capture."""
    from duchess_engine import Board, search

    # White knight can capture undefended black queen on d6
    b = Board("7k/8/3q4/8/4N3/8/8/K7 w - - 0 1")
    result = search(b, 3)
    assert result.best_move.to_uci() == "e4d6"
    assert result.score > 0


def test_is_checkmate():
    """is_checkmate should detect checkmate."""
    from duchess_engine import Board, is_checkmate, is_stalemate

    # Scholar's mate final position — black is checkmated
    b = Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    # Make Qxf7#
    from duchess_engine import Move
    b.make_move(Move.from_uci("h5f7"))
    assert is_checkmate(b)
    assert not is_stalemate(b)


def test_is_stalemate():
    """is_stalemate should detect stalemate."""
    from duchess_engine import Board, is_checkmate, is_stalemate

    # Classic stalemate: black king on a8, white queen on b6, white king on c8
    # Wait — let me use a known stalemate position
    # Black king a1, white king a3, white queen b3 — black to move, no legal moves, not in check
    b = Board("8/8/8/8/8/KQ6/8/k7 b - - 0 1")
    assert is_stalemate(b)
    assert not is_checkmate(b)


def test_move_repr():
    """Move __repr__ should show UCI notation."""
    from duchess_engine import Move

    m = Move.from_uci("e2e4")
    assert "e2e4" in repr(m)


def test_board_repr():
    """Board __repr__ should show FEN."""
    from duchess_engine import Board

    b = Board()
    assert "rnbqkbnr" in repr(b)
