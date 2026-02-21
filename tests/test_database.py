import pytest
from sqlalchemy.exc import IntegrityError

from duchess.models import User, Game, Move


def test_create_user(db_session):
    user = User(username="alice", email="alice@example.com", whatsapp="+1234567890")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.username == "alice"


def test_unique_username(db_session):
    db_session.add(User(username="bob"))
    db_session.commit()

    db_session.add(User(username="bob"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_game(db_session):
    white = User(username="white_player")
    black = User(username="black_player")
    db_session.add_all([white, black])
    db_session.commit()

    game = Game(white_player_id=white.id, black_player_id=black.id)
    db_session.add(game)
    db_session.commit()

    assert game.id is not None
    assert game.status == "active"
    assert game.fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    assert game.white_player.username == "white_player"
    assert game.black_player.username == "black_player"


def test_record_moves(db_session):
    white = User(username="p1")
    black = User(username="p2")
    db_session.add_all([white, black])
    db_session.commit()

    game = Game(white_player_id=white.id, black_player_id=black.id)
    db_session.add(game)
    db_session.commit()

    move1 = Move(game_id=game.id, uci="e2e4")
    move2 = Move(game_id=game.id, uci="e7e5")
    db_session.add_all([move1, move2])
    db_session.commit()

    assert len(game.moves) == 2
    assert game.moves[0].uci == "e2e4"
    assert game.moves[1].uci == "e7e5"
    assert move1.timestamp is not None


def test_unique_email(db_session):
    db_session.add(User(username="u1", email="same@example.com"))
    db_session.commit()

    db_session.add(User(username="u2", email="same@example.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()
