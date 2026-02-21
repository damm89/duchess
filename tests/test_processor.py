"""Tests for processor — game flow, commands, and move handling."""
from duchess.board import DuchessBoard, STARTING_FEN
from duchess.models import User, Game, Move
from duchess.processor import process_email_move


def _plain(sender, move, db):
    """Helper: call process_email_move and return just the plain text."""
    plain, html = process_email_move(sender, move, db)
    return plain


def test_move_without_game(db_session):
    """Sending a move with no active game should prompt to start one."""
    plain = _plain("nogame@test.com", "e2e4", db_session)
    assert "start white" in plain.lower() or "start black" in plain.lower()
    user = db_session.query(User).filter(User.email == "nogame@test.com").first()
    games = db_session.query(Game).filter(
        (Game.white_player_id == user.id) | (Game.black_player_id == user.id)
    ).all()
    assert len(games) == 0


def test_new_game_and_move(db_session):
    """Start a game, then make a move."""
    _plain("player@test.com", "start white", db_session)
    plain = _plain("player@test.com", "e2e4", db_session)
    assert "You played e4" in plain


def test_invalid_move_shows_board(db_session):
    _plain("badmove@test.com", "start white", db_session)
    plain, html = process_email_move("badmove@test.com", "e2e5", db_session)
    assert "Invalid move" in plain
    assert "<table" in html


def test_existing_game_continues(db_session):
    _plain("cont@test.com", "start white", db_session)
    plain1 = _plain("cont@test.com", "e2e4", db_session)
    assert "You played e4" in plain1

    user = db_session.query(User).filter(User.email == "cont@test.com").first()
    game = db_session.query(Game).filter(
        Game.white_player_id == user.id,
        Game.status == "active"
    ).first()

    board = DuchessBoard(game.fen)
    legal_move = board.legal_moves[0]

    plain2 = _plain("cont@test.com", legal_move.to_uci(), db_session)
    assert "You played" in plain2

    moves = db_session.query(Move).filter(Move.game_id == game.id).all()
    assert len(moves) == 4


def test_san_move(db_session):
    _plain("san@test.com", "start white", db_session)
    plain = _plain("san@test.com", "Nf3", db_session)
    assert "You played Nf3" in plain


def test_full_flow_integration(db_session):
    """Integration test: start game -> move -> DB update -> response with board."""
    process_email_move("integration@test.com", "start white", db_session)
    plain, html = process_email_move("integration@test.com", "e2e4", db_session)
    assert "You played e4" in plain
    assert "My move:" in plain
    assert "<table" in html

    user = db_session.query(User).filter(User.email == "integration@test.com").first()
    game = db_session.query(Game).filter(Game.white_player_id == user.id, Game.status == "active").first()
    assert game.fen != STARTING_FEN
    assert game.pgn is not None and len(game.pgn.strip()) > 0

    moves = db_session.query(Move).filter(Move.game_id == game.id).all()
    assert len(moves) == 2


# --- Command tests ---

def test_help_command_no_game(db_session):
    plain = _plain("help@test.com", "help", db_session)
    assert "Commands" in plain
    assert "start white" in plain


def test_help_command_with_game(db_session):
    process_email_move("helpgame@test.com", "start white", db_session)
    plain, html = process_email_move("helpgame@test.com", "help", db_session)
    assert "Commands" in plain
    assert "<table" in html


def test_start_white(db_session):
    plain, html = process_email_move("sw@test.com", "start white", db_session)
    assert "You are White" in plain
    assert "<table" in html

    user = db_session.query(User).filter(User.email == "sw@test.com").first()
    game = db_session.query(Game).filter(Game.white_player_id == user.id, Game.status == "active").first()
    assert game is not None
    assert game.fen == STARTING_FEN


def test_start_black(db_session):
    plain, html = process_email_move("sb@test.com", "start black", db_session)
    assert "You are Black" in plain
    assert "My move:" in plain
    assert "<table" in html

    user = db_session.query(User).filter(User.email == "sb@test.com").first()
    game = db_session.query(Game).filter(Game.black_player_id == user.id, Game.status == "active").first()
    assert game is not None
    assert game.fen != STARTING_FEN
    moves = db_session.query(Move).filter(Move.game_id == game.id).all()
    assert len(moves) == 1


def test_start_abandons_previous_game(db_session):
    process_email_move("abandon@test.com", "start white", db_session)
    user = db_session.query(User).filter(User.email == "abandon@test.com").first()
    first_game = db_session.query(Game).filter(Game.white_player_id == user.id, Game.status == "active").first()
    first_game_id = first_game.id

    process_email_move("abandon@test.com", "start white", db_session)
    db_session.refresh(first_game)
    assert first_game.status == "abandoned"

    active = db_session.query(Game).filter(
        Game.white_player_id == user.id, Game.status == "active"
    ).first()
    assert active is not None
    assert active.id != first_game_id


def test_resign_shows_board(db_session):
    process_email_move("resign@test.com", "start white", db_session)
    process_email_move("resign@test.com", "e2e4", db_session)
    plain, html = process_email_move("resign@test.com", "resign", db_session)
    assert "resigned" in plain.lower()
    assert "<table" in html

    user = db_session.query(User).filter(User.email == "resign@test.com").first()
    game = db_session.query(Game).filter(Game.white_player_id == user.id).first()
    assert game.status == "resigned"


def test_resign_no_game(db_session):
    plain = _plain("noresign@test.com", "resign", db_session)
    assert "No active game" in plain
    assert "start" in plain.lower()


def test_status(db_session):
    process_email_move("stat@test.com", "start white", db_session)
    process_email_move("stat@test.com", "e2e4", db_session)
    plain, html = process_email_move("stat@test.com", "status", db_session)
    assert "to move" in plain
    assert "<table" in html


def test_status_no_game(db_session):
    plain = _plain("nostat@test.com", "status", db_session)
    assert "No active game" in plain
    assert "start" in plain.lower()
