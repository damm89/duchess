#!/usr/bin/env python3
# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""
Engine Gauntlet — play Duchess against any external UCI engine.

Games are saved to the MasterGame PostgreSQL table (training_use=True),
making them immediately available as training data for the NNUE pipeline.

Usage:
    python nnue/gauntlet.py --engine2 /usr/local/bin/stockfish --games 100 --time 0.1
"""
import argparse
import datetime
import logging
import multiprocessing
import os
import random
import signal
import sys
import time
from typing import Optional

import chess
import chess.engine
import chess.pgn
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from duchess.database import SessionLocal
from duchess.models import MasterGame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def play_game(
    engine1_path: str,
    engine2_path: str,
    game_index: int,
    depth: Optional[int],
    time_per_move: float,
    random_plies: int,
    nnue_path: Optional[str],
    syzygy_path: Optional[str],
) -> Optional[dict]:
    """
    Play one game between engine1 (Duchess) and engine2.
    engine1 plays White in even-indexed games, Black in odd-indexed games.
    Returns a dict ready for MasterGame insertion, or None on error.
    """
    duchess_is_white = (game_index % 2 == 0)

    try:
        e1 = chess.engine.SimpleEngine.popen_uci(engine1_path)
        e2 = chess.engine.SimpleEngine.popen_uci(engine2_path)

        if nnue_path:
            try:
                e1.configure({"NNUEFile": nnue_path})
            except Exception:
                pass  # Engine may not support it

        if syzygy_path:
            for eng in (e1, e2):
                try:
                    eng.configure({"SyzygyPath": syzygy_path})
                except Exception:
                    pass

    except Exception as exc:
        logger.error(f"Failed to start engines: {exc}")
        return None

    try:
        board = chess.Board()
        game = chess.pgn.Game()

        # Random opening plies for diversity
        for _ in range(random_plies):
            if board.is_game_over():
                break
            board.push(random.choice(list(board.legal_moves)))

        game.setup(board)

        engine1_name = os.path.basename(engine1_path)
        engine2_name = os.path.basename(engine2_path)
        white_name = engine1_name if duchess_is_white else engine2_name
        black_name = engine2_name if duchess_is_white else engine1_name

        game.headers["Event"] = f"Duchess Gauntlet: {engine1_name} vs {engine2_name}"
        game.headers["White"] = white_name
        game.headers["Black"] = black_name
        game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")

        # Build limit
        limit = chess.engine.Limit(depth=depth) if depth else chess.engine.Limit(time=time_per_move)

        node = game
        while not board.is_game_over():
            # Whose turn is it?
            white_to_move = (board.turn == chess.WHITE)
            duchess_to_move = (white_to_move == duchess_is_white)
            active_engine = e1 if duchess_to_move else e2

            result = active_engine.play(board, limit)
            if not result.move:
                break

            try:
                board.push(result.move)
            except ValueError:
                logger.warning(f"Illegal move {result.move} in {board.fen()}")
                e1.quit()
                e2.quit()
                return None

            node = node.add_variation(result.move)

        game.headers["Result"] = board.result()
        e1.quit()
        e2.quit()

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        pgn_string = game.accept(exporter)

        return {
            "event":      game.headers.get("Event"),
            "date":       game.headers.get("Date"),
            "white":      game.headers.get("White"),
            "black":      game.headers.get("Black"),
            "result":     game.headers.get("Result"),
            "white_elo":  0,
            "black_elo":  0,
            "eco":        game.headers.get("ECO", ""),
            "move_text":  pgn_string,
            "training_use": True,
        }

    except Exception as exc:
        for eng in (e1, e2):
            try:
                eng.quit()
            except Exception:
                pass
        logger.error(f"Worker crashed: {exc}")
        return None


def worker_init():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def run_gauntlet(
    engine1_path: str,
    engine2_path: str,
    num_games: int,
    threads: int,
    depth: Optional[int],
    time_per_move: float,
    random_plies: int,
    nnue_path: Optional[str],
    syzygy_path: Optional[str],
):
    e1_name = os.path.basename(engine1_path)
    e2_name = os.path.basename(engine2_path)
    logger.info(f"Starting gauntlet: {e1_name} vs {e2_name} — {num_games} games, {threads} workers")

    db: Session = SessionLocal()
    completed = 0
    batch: list[dict] = []
    batch_size = 20
    start_time = time.time()

    try:
        with multiprocessing.Pool(processes=threads, initializer=worker_init) as pool:
            jobs = [
                pool.apply_async(play_game, (
                    engine1_path, engine2_path, idx,
                    depth, time_per_move, random_plies,
                    nnue_path, syzygy_path,
                ))
                for idx in range(num_games)
            ]

            iterator = enumerate(jobs)
            if HAS_TQDM:
                from tqdm import tqdm
                iterator = enumerate(tqdm(jobs, total=num_games, desc="Gauntlet", unit="game", dynamic_ncols=True))

            for _, job in iterator:
                result = job.get()
                if result:
                    batch.append(result)
                    completed += 1
                    if len(batch) >= batch_size:
                        try:
                            db.bulk_insert_mappings(MasterGame, batch)
                            db.commit()
                            batch.clear()
                        except Exception as exc:
                            db.rollback()
                            logger.error(f"DB insert failed: {exc}")

            if batch:
                try:
                    db.bulk_insert_mappings(MasterGame, batch)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.error(f"DB insert (final batch) failed: {exc}")

    except KeyboardInterrupt:
        logger.warning("Interrupted — killing workers.")
        pool.terminate()
        pool.join()
    finally:
        db.close()

    elapsed = time.time() - start_time
    rate = completed / elapsed if elapsed > 0 else 0
    logger.info(f"Gauntlet complete — {completed}/{num_games} games saved in {elapsed:.1f}s ({rate:.2f} games/sec)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play Duchess against an external UCI engine and save games for RL training.")
    parser.add_argument("--engine1", type=str, default="engine/build/duchess_cli", help="Path to Duchess engine binary.")
    parser.add_argument("--engine2", type=str, required=True, help="Path to the opponent UCI engine (e.g. stockfish).")
    parser.add_argument("--games", type=int, default=100, help="Number of games to play.")
    parser.add_argument("--threads", type=int, default=4, help="Number of parallel game workers.")
    parser.add_argument("--depth", type=int, default=None, help="Fixed search depth per move. If omitted, --time is used.")
    parser.add_argument("--time", type=float, default=0.1, dest="time_per_move", help="Seconds per move (used when --depth is not set).")
    parser.add_argument("--random-plies", type=int, default=8, help="Random opening half-moves for diversity.")
    parser.add_argument("--nnue", type=str, default=None, help="Optional NNUE weights to load in Duchess.")
    parser.add_argument("--syzygy", type=str, default=None, help="Optional Syzygy tablebase directory path.")

    args = parser.parse_args()

    for path, label in [(args.engine1, "engine1"), (args.engine2, "engine2")]:
        if not os.path.exists(path):
            logger.error(f"{label} binary not found: {path}")
            sys.exit(1)

    run_gauntlet(
        engine1_path=args.engine1,
        engine2_path=args.engine2,
        num_games=args.games,
        threads=args.threads,
        depth=args.depth,
        time_per_move=args.time_per_move,
        random_plies=args.random_plies,
        nnue_path=args.nnue,
        syzygy_path=args.syzygy,
    )
