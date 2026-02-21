"""ChessEngine — wraps the C++ duchess_engine search."""
import duchess_engine
from duchess_engine import Board as _CppBoard


class ChessEngine:
    def __init__(self):
        pass  # No external process needed

    def get_best_move(self, fen, depth=5):
        board = _CppBoard(fen)
        result = duchess_engine.search(board, depth)
        return result.best_move.to_uci()

    def get_best_move_timed(self, fen, time_ms=1000):
        board = _CppBoard(fen)
        result = duchess_engine.search_timed(board, time_ms)
        return result.best_move.to_uci()

    def evaluate_position(self, fen):
        board = _CppBoard(fen)
        # Check for mate/stalemate first
        if duchess_engine.is_checkmate(board):
            # Side to move is mated
            return {"mate": 0, "depth": 0}
        score = duchess_engine.evaluate(board)
        # Convert to white's perspective
        if board.side_to_move() == duchess_engine.Color.BLACK:
            score = -score
        return {"cp": score, "depth": 0}

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
