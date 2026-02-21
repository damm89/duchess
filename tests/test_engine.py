"""Tests for ChessEngine — wraps the C++ duchess_engine search."""
from duchess.board import STARTING_FEN, DuchessBoard


def test_engine_starts(engine):
    assert engine is not None


def test_get_best_move_starting_position(engine):
    move = engine.get_best_move(STARTING_FEN)
    assert len(move) in (4, 5)
    board = DuchessBoard(STARTING_FEN)
    uci_moves = [m.to_uci() for m in board.legal_moves]
    assert move in uci_moves


def test_evaluate_position_starting(engine):
    result = engine.evaluate_position(STARTING_FEN)
    assert "cp" in result
    assert -100 < result["cp"] < 100


def test_evaluate_position_mate(engine):
    # Position where white is mated (fool's mate setup, white to move, no escape)
    fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    result = engine.evaluate_position(fen)
    assert "mate" in result
