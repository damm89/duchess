"""commands.py — defines the Command Pattern for handling text-based moves."""
from abc import ABC, abstractmethod


class Command(ABC):
    @abstractmethod
    def match(self, message: str) -> bool:
        """Return True if this command should handle the given message."""
        pass

    @abstractmethod
    def execute(self, message: str, user, db_session) -> tuple[str, str]:
        """Execute the command and return (plain_text, html_text)."""
        pass


class HelpCommand(Command):
    def match(self, message: str) -> bool:
        return message.strip().lower() in ("help", "?")

    def execute(self, message: str, user, db_session) -> tuple[str, str]:
        from duchess.processor import _get_active_game, _make_response, HELP_TEXT
        from duchess.board import DuchessBoard

        game = _get_active_game(user, db_session)
        if game:
            board = DuchessBoard(game.fen)
            return _make_response(HELP_TEXT, board)
        return _make_response(HELP_TEXT)


class ResignCommand(Command):
    def match(self, message: str) -> bool:
        return message.strip().lower() in ("resign", "end")

    def execute(self, message: str, user, db_session) -> tuple[str, str]:
        from duchess.processor import _get_active_game, _make_response
        from duchess.board import DuchessBoard

        game = _get_active_game(user, db_session)
        if game is None:
            return _make_response("No active game to resign. Send 'start white' or 'start black' to begin.")
        board = DuchessBoard(game.fen)
        game.status = "resigned"
        db_session.commit()
        return _make_response("Game resigned.", board)


class StatusCommand(Command):
    def match(self, message: str) -> bool:
        return message.strip().lower() in ("status", "show")

    def execute(self, message: str, user, db_session) -> tuple[str, str]:
        from duchess.processor import _get_active_game, _make_response
        from duchess.board import DuchessBoard

        game = _get_active_game(user, db_session)
        if game is None:
            return _make_response("No active game. Send 'start white' or 'start black' to begin.")
        board = DuchessBoard(game.fen)
        turn = "White" if board.turn == "white" else "Black"
        return _make_response(f"Current game ({turn} to move):", board)


class StartCommand(Command):
    def match(self, message: str) -> bool:
        return message.strip().lower().startswith("start")

    def execute(self, message: str, user, db_session) -> tuple[str, str]:
        from duchess.processor import _handle_start
        color = "black" if "black" in message.strip().lower() else "white"
        return _handle_start(user, color, db_session)


class MoveCommand(Command):
    def match(self, message: str) -> bool:
        # Fallback command, always matches if reached
        return True

    def execute(self, message: str, user, db_session) -> tuple[str, str]:
        from duchess.processor import _handle_move
        return _handle_move(message, user, db_session)
