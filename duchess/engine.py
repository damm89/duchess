# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""ChessEngine — wraps the UCI engine subprocess for search."""
from duchess.engine_wrapper import get_engine


class ChessEngine:
    def __init__(self):
        pass

    def get_best_move(self, fen, depth=5):
        engine = get_engine()
        engine.set_position_fen(fen)
        return engine.go_depth(depth)

    def get_best_move_timed(self, fen, time_ms=1000, info_cb=None):
        engine = get_engine()
        engine.set_position_fen(fen)
        return engine.go_movetime(time_ms, info_cb=info_cb)

    def evaluate_position(self, fen):
        engine = get_engine()
        engine.set_position_fen(fen)
        result = engine.evaluate()
        if "mate" in result:
            return {"mate": result["mate"], "depth": 0}
        # eval returns score from side-to-move perspective;
        # convert to white's perspective
        cp = result["cp"]
        parts = fen.split()
        if len(parts) >= 2 and parts[1] == "b":
            cp = -cp
        return {"cp": cp, "depth": 0}

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
