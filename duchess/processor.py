from duchess.chess_types import Move as _Move

from duchess.board import DuchessBoard, InvalidMoveError, IllegalMoveError, AmbiguousMoveError
from duchess.engine import ChessEngine
from duchess.models import Game, Move, User

_engine = None

EMAIL_FOOTER = """
---
Duchess Chess Bot - Commands:
  start white  - Start a new game as White
  start black  - Start a new game as Black
  resign       - Resign the current game
  status       - Show the current board
  help         - Show this message
  Moves: UCI (e.g. e2e4) or SAN (e.g. Nf3)
  Subject must be: duchess"""

HTML_FOOTER = """<hr style="margin:16px 0;border:none;border-top:1px solid #ccc;">
<pre style="font-family:monospace;font-size:13px;color:#666;">Duchess Chess Bot - Commands:
  start white  - Start a new game as White
  start black  - Start a new game as Black
  resign       - Resign the current game
  status       - Show the current board
  help         - Show this message
  Moves: UCI (e.g. e2e4) or SAN (e.g. Nf3)
  Subject must be: duchess</pre>"""

HELP_TEXT = EMAIL_FOOTER.lstrip("\n-")


def get_engine():
    global _engine
    if _engine is None:
        _engine = ChessEngine()
    return _engine


def _get_or_create_user(sender_email, db_session):
    user = db_session.query(User).filter(User.email == sender_email).first()
    if user is None:
        user = User(username=sender_email, email=sender_email)
        db_session.add(user)
        db_session.commit()
    return user


def _get_engine_user(db_session):
    engine_user = db_session.query(User).filter(User.username == "stockfish").first()
    if engine_user is None:
        engine_user = User(username="stockfish")
        db_session.add(engine_user)
        db_session.commit()
    return engine_user


def _get_active_game(user, db_session):
    return (
        db_session.query(Game)
        .filter(
            ((Game.white_player_id == user.id) | (Game.black_player_id == user.id)),
            Game.status == "active",
        )
        .first()
    )


def _make_response(text, board=None):
    """Return (plain_text, html) tuple."""
    plain = text + EMAIL_FOOTER
    if board is not None:
        html = f"<p>{_text_to_html(text)}</p>{board.to_html()}{HTML_FOOTER}"
    else:
        html = f"<p>{_text_to_html(text)}</p>{HTML_FOOTER}"
    return plain, html


def _text_to_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


def _handle_start(user, color, db_session):
    active = _get_active_game(user, db_session)
    if active is not None:
        active.status = "abandoned"
        db_session.commit()

    engine_user = _get_engine_user(db_session)

    if color == "white":
        game = Game(white_player_id=user.id, black_player_id=engine_user.id)
    else:
        game = Game(white_player_id=engine_user.id, black_player_id=user.id)

    db_session.add(game)
    db_session.commit()

    board = DuchessBoard(game.fen)

    if color == "black":
        engine = get_engine()
        engine_uci = engine.get_best_move(board.fen())
        engine_move = _Move.from_uci(engine_uci)
        engine_san = board.san(engine_move)
        board.push(engine_move)

        db_session.add(Move(game_id=game.id, uci=engine_uci))
        game.fen = board.fen()
        game.pgn = f" 1. {engine_san}"
        db_session.commit()

        return _make_response(
            f"New game started! You are Black.\nMy move: {engine_san} ({engine_uci})", board
        )

    return _make_response("New game started! You are White. Your move.", board)


def _handle_resign(user, db_session):
    game = _get_active_game(user, db_session)
    if game is None:
        return _make_response("No active game to resign. Send 'start white' or 'start black' to begin.")
    board = DuchessBoard(game.fen)
    game.status = "resigned"
    db_session.commit()
    return _make_response("Game resigned.", board)


def _handle_status(user, db_session):
    game = _get_active_game(user, db_session)
    if game is None:
        return _make_response("No active game. Send 'start white' or 'start black' to begin.")
    board = DuchessBoard(game.fen)
    turn = "White" if board.turn == "white" else "Black"
    return _make_response(f"Current game ({turn} to move):", board)


def process_email_move(sender_email, move_str, db_session):
    return _process(sender_email, move_str, db_session)


def _process(sender_email, move_str, db_session):
    user = _get_or_create_user(sender_email, db_session)

    cmd = move_str.strip().lower()
    if cmd in ("help", "?"):
        game = _get_active_game(user, db_session)
        if game:
            board = DuchessBoard(game.fen)
            return _make_response(HELP_TEXT, board)
        return _make_response(HELP_TEXT)
    if cmd in ("resign", "end"):
        return _handle_resign(user, db_session)
    if cmd in ("status", "show"):
        return _handle_status(user, db_session)
    if cmd.startswith("start"):
        color = "black" if "black" in cmd else "white"
        return _handle_start(user, color, db_session)

    game = _get_active_game(user, db_session)

    if game is None:
        return _make_response(
            "You don't have an active game. Send 'start white' or 'start black' to begin a new game."
        )

    board = DuchessBoard(game.fen)

    # Try UCI first
    player_move = None
    try:
        candidate = _Move.from_uci(move_str)
        legal = board.legal_moves
        for lm in legal:
            if lm.from_sq == candidate.from_sq and lm.to_sq == candidate.to_sq and lm.promotion == candidate.promotion:
                player_move = lm
                break
    except (ValueError, RuntimeError):
        pass

    # Try SAN
    if player_move is None:
        try:
            player_move = board.parse_san(move_str)
        except (InvalidMoveError, IllegalMoveError, AmbiguousMoveError):
            legal = board.legal_moves
            return _make_response(
                f"Invalid move: '{move_str}'. Legal moves: {', '.join(m.to_uci() for m in legal)}",
                board
            )

    player_uci = player_move.to_uci()
    player_san = board.san(player_move)
    board.push(player_move)

    move_number = len(game.moves) + 1
    db_session.add(Move(game_id=game.id, uci=player_uci))
    db_session.commit()

    if board.is_game_over():
        game.fen = board.fen()
        game.status = "completed"
        game.pgn = (game.pgn or "") + f" {move_number}. {player_san}"
        result = board.result()
        db_session.commit()
        return _make_response(f"You played {player_san}. Game over! Result: {result}", board)

    engine = get_engine()
    engine_uci = engine.get_best_move(board.fen())
    engine_move = _Move.from_uci(engine_uci)
    engine_san = board.san(engine_move)
    board.push(engine_move)

    db_session.add(Move(game_id=game.id, uci=engine_uci))

    game.fen = board.fen()
    game.pgn = (game.pgn or "") + f" {move_number}. {player_san} {engine_san}"

    if board.is_game_over():
        game.status = "completed"
        result = board.result()
        db_session.commit()
        return _make_response(
            f"You played {player_san}.\nMy move: {engine_san} ({engine_uci})\n\nGame over! Result: {result}", board
        )

    db_session.commit()
    return _make_response(f"You played {player_san}.\nMy move: {engine_san} ({engine_uci})", board)
