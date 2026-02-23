"""Tests for DuchessBoard — wraps the C++ duchess_engine."""
from duchess.board import DuchessBoard


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_board_initialization():
    board = DuchessBoard()
    assert board.fen() == STARTING_FEN


def test_make_legal_move():
    board = DuchessBoard()
    assert board.make_move_uci("e2e4") is True
    assert board.turn == "black"


def test_make_illegal_move():
    board = DuchessBoard()
    assert board.make_move_uci("e2e5") is False
    assert board.turn == "white"


def test_fen_generation():
    board = DuchessBoard()
    board.make_move_uci("e2e4")
    fen = board.get_fen()
    assert fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def test_legal_moves():
    board = DuchessBoard()
    moves = board.legal_moves
    uci_list = [m.to_uci() for m in moves]
    assert "e2e4" in uci_list
    assert len(moves) == 20


def test_push_and_pop():
    board = DuchessBoard()
    from duchess.chess_types import Move
    m = Move.from_uci("e2e4")
    board.push(m)
    assert board.turn == "black"


def test_san_pawn_move():
    board = DuchessBoard()
    from duchess.chess_types import Move
    m = Move.from_uci("e2e4")
    assert board.san(m) == "e4"


def test_san_knight_move():
    board = DuchessBoard()
    from duchess.chess_types import Move
    m = Move.from_uci("g1f3")
    assert board.san(m) == "Nf3"


def test_san_capture():
    board = DuchessBoard("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2")
    from duchess.chess_types import Move
    m = Move.from_uci("e4d5")
    assert board.san(m) == "exd5"


def test_san_castling():
    board = DuchessBoard("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    from duchess.chess_types import Move
    m = Move.from_uci("e1g1")
    assert board.san(m) == "O-O"


def test_parse_san_pawn():
    board = DuchessBoard()
    m = board.parse_san("e4")
    assert m.to_uci() == "e2e4"


def test_parse_san_knight():
    board = DuchessBoard()
    m = board.parse_san("Nf3")
    assert m.to_uci() == "g1f3"


def test_is_game_over_starting():
    board = DuchessBoard()
    assert board.is_game_over() is False


def test_result_checkmate():
    # Scholar's mate final: after Qxf7#
    board = DuchessBoard("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    assert board.is_game_over() is True
    assert board.result() == "1-0"


def test_to_html():
    board = DuchessBoard()
    html = board.to_html()
    assert "<table" in html


def test_pretty():
    board = DuchessBoard()
    text = board.pretty()
    assert "a b c d e f g h" in text
