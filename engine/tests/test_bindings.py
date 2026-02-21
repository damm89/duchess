"""Phase 2 Step 2.1 — Verify duchess_engine pybind11 module can be imported."""
import pytest


def test_import_duchess_engine():
    """The module should be importable."""
    import duchess_engine  # noqa: F401


def test_create_board_default():
    """Creating a Board with no args gives the starting position."""
    from duchess_engine import Board

    b = Board()
    fen = b.to_fen()
    assert fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_create_board_from_fen():
    """Creating a Board from a FEN string works."""
    from duchess_engine import Board

    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    b = Board(fen)
    assert b.to_fen() == fen
