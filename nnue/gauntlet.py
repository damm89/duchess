#!/usr/bin/env python3
# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""
Engine Gauntlet — play Duchess against any external UCI engine.

Games are saved to the MasterGame PostgreSQL table (training_use=True),
making them immediately available as training data for the NNUE pipeline.

Usage:
    # Fixed time per move (simple mode):
    python nnue/gauntlet.py --engine2 /path/to/opponent --games 20 --time 5.0

    # Game clock with increment (realistic mode):
    python nnue/gauntlet.py --engine2 /path/to/opponent --games 20 --clock 180 --inc 2

    # Fixed depth:
    python nnue/gauntlet.py --engine2 /path/to/opponent --games 20 --depth 10
"""
import argparse
import datetime
import logging
import math
import multiprocessing
import os
import random
import signal
import sys
import time
import resource
from typing import Optional

# Force file descriptor limits up to handle massive parallel engine gauntlets
try:
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target_limit = min(100000, hard)
    resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard))
except Exception as e:
    print(f"WARNING: Failed to increase RLIMIT_NOFILE: {e}")

import chess
import chess.engine
import chess.pgn
import chess.polyglot
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
    clock_time: Optional[float],
    clock_inc: float,
    random_plies: int,
    nnue_path: Optional[str],
    syzygy_path: Optional[str],
    book_path: Optional[str] = None,
    iteration: Optional[int] = None,
) -> Optional[dict]:
    """
    Play one game between engine1 (Duchess) and engine2.
    engine1 plays White in even-indexed games, Black in odd-indexed games.
    Returns a dict with game data and result metadata, or None on error.
    """
    duchess_is_white = (game_index % 2 == 0)

    try:
        e1 = chess.engine.SimpleEngine.popen_uci(engine1_path)
        e2 = chess.engine.SimpleEngine.popen_uci(engine2_path)

        if nnue_path:
            try:
                e1.configure({"NNUEFile": nnue_path})
            except Exception:
                pass

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

        # Opening phase — use book moves if available, else random
        if book_path:
            with chess.polyglot.open_reader(book_path) as reader:
                for _ in range(random_plies):
                    if board.is_game_over():
                        break
                    entries = list(reader.find_all(board))
                    if entries:
                        moves = [e.move for e in entries]
                        weights = [e.weight for e in entries]
                        board.push(random.choices(moves, weights=weights, k=1)[0])
                    else:
                        break
        else:
            for _ in range(random_plies):
                if board.is_game_over():
                    break
                board.push(random.choice(list(board.legal_moves)))

        game.setup(board)

        engine1_name = os.path.basename(engine1_path)
        engine2_name = os.path.basename(engine2_path)
        white_name = engine1_name if duchess_is_white else engine2_name
        black_name = engine2_name if duchess_is_white else engine1_name

        event_name = f"Gauntlet: {engine1_name} vs {engine2_name} Iteration {iteration}" if iteration else f"Gauntlet: {engine1_name} vs {engine2_name}"
        game.headers["Event"] = event_name
        game.headers["White"] = white_name
        game.headers["Black"] = black_name
        game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")

        # Clock state (seconds remaining per side)
        use_clock = clock_time is not None and depth is None
        if use_clock:
            clocks = {chess.WHITE: clock_time, chess.BLACK: clock_time}
            game.headers["TimeControl"] = f"{int(clock_time)}+{int(clock_inc)}"

        node = game
        while not board.is_game_over():
            white_to_move = (board.turn == chess.WHITE)
            duchess_to_move = (white_to_move == duchess_is_white)
            active_engine = e1 if duchess_to_move else e2

            # Build the search limit
            if depth:
                limit = chess.engine.Limit(depth=depth)
            elif use_clock:
                wt = clocks[chess.WHITE]
                bt = clocks[chess.BLACK]
                limit = chess.engine.Limit(
                    white_clock=wt, black_clock=bt,
                    white_inc=clock_inc, black_inc=clock_inc,
                )
            else:
                limit = chess.engine.Limit(time=time_per_move)

            move_start = time.monotonic()
            result = active_engine.play(board, limit)
            move_elapsed = time.monotonic() - move_start

            if not result.move:
                break

            # Update clock
            if use_clock:
                clocks[board.turn] -= move_elapsed
                clocks[board.turn] += clock_inc
                # Flag fall
                if clocks[board.turn] <= 0:
                    if board.turn == chess.WHITE:
                        game.headers["Result"] = "0-1"
                    else:
                        game.headers["Result"] = "1-0"
                    e1.quit()
                    e2.quit()
                    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
                    pgn_string = game.accept(exporter)
                    return _build_result(game, pgn_string, engine1_name, duchess_is_white)

            try:
                board.push(result.move)
            except ValueError:
                logger.warning(f"Illegal move {result.move} in {board.fen()}")
                e1.quit()
                e2.quit()
                return None

            node = node.add_variation(result.move)

        if "Result" not in game.headers or game.headers["Result"] == "*":
            game.headers["Result"] = board.result()
        e1.quit()
        e2.quit()

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        pgn_string = game.accept(exporter)
        return _build_result(game, pgn_string, engine1_name, duchess_is_white)

    except Exception as exc:
        import traceback
        for eng in (e1, e2):
            try:
                eng.quit()
            except Exception:
                pass
        logger.error(f"Worker crashed: {exc!r}\n{traceback.format_exc()}")
        return None


def _build_result(game, pgn_string: str, engine1_name: str, duchess_is_white: bool) -> dict:
    """Build the result dict with game data and match metadata."""
    result_str = game.headers.get("Result", "*")

    # Determine outcome from engine1's perspective
    if result_str == "1-0":
        e1_outcome = "win" if duchess_is_white else "loss"
    elif result_str == "0-1":
        e1_outcome = "loss" if duchess_is_white else "win"
    elif result_str == "1/2-1/2":
        e1_outcome = "draw"
    else:
        e1_outcome = "unknown"

    return {
        "event":      game.headers.get("Event"),
        "date":       game.headers.get("Date"),
        "white":      game.headers.get("White"),
        "black":      game.headers.get("Black"),
        "result":     result_str,
        "white_elo":  0,
        "black_elo":  0,
        "eco":        game.headers.get("ECO", ""),
        "move_text":  pgn_string,
        "training_use": True,
        # Match metadata (not stored in DB, used for statistics)
        "_e1_outcome": e1_outcome,
        "_e1_color": "White" if duchess_is_white else "Black",
    }


def worker_init():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _elo_diff(wins: int, draws: int, losses: int) -> str:
    """Estimate Elo difference from match results."""
    total = wins + draws + losses
    if total == 0:
        return "N/A"
    score = (wins + 0.5 * draws) / total
    if score <= 0 or score >= 1:
        return "+inf" if score >= 1 else "-inf"
    elo = -400 * math.log10(1 / score - 1)
    return f"{elo:+.0f}"


def run_gauntlet(
    engine1_path: str,
    engine2_path: str,
    num_games: int,
    threads: int,
    depth: Optional[int],
    time_per_move: float,
    clock_time: Optional[float],
    clock_inc: float,
    random_plies: int,
    nnue_path: Optional[str],
    syzygy_path: Optional[str],
    book_path: Optional[str] = None,
    iteration: Optional[int] = None,
    no_db: bool = False,
):
    e1_name = os.path.basename(engine1_path)
    e2_name = os.path.basename(engine2_path)

    # Describe time control
    if depth:
        tc_desc = f"depth {depth}"
    elif clock_time:
        tc_desc = f"{clock_time:.0f}s+{clock_inc:.0f}s"
    else:
        tc_desc = f"{time_per_move:.1f}s/move"

    if no_db:
        db = None
        logger.info(f"Starting gauntlet: {e1_name} vs {e2_name} — {num_games} games, {tc_desc}, {threads} workers (no DB)")
    else:
        db: Session = SessionLocal()

        # Auto-resume logic: Check if games for today's iteration already exist in the database
        try:
            gauntlet_event_name = f"Gauntlet: {e1_name} vs {e2_name} Iteration {iteration}" if iteration else f"Gauntlet: {e1_name} vs {e2_name}"
            existing_games = db.query(MasterGame).filter(
                MasterGame.event == gauntlet_event_name,
                MasterGame.training_use.is_(True)
            ).count()
        except Exception as e:
            logger.warning(f"Could not check existing games: {e}")
            existing_games = 0

        if existing_games >= num_games:
            logger.info(f"Skipping gauntlet: found {existing_games} existing games for today (Target: {num_games})")
            db.close()
            return
        elif existing_games > 0:
            logger.info(f"Resuming gauntlet: found {existing_games} existing games. Playing {num_games - existing_games} more.")
            num_games -= existing_games
        else:
            logger.info(f"Starting gauntlet: {e1_name} vs {e2_name} — {num_games} games, {tc_desc}, {threads} workers")

    completed = 0
    batch: list[dict] = []
    batch_size = 20
    start_time = time.time()

    # Statistics
    e1_wins, e1_draws, e1_losses = 0, 0, 0

    try:
        with multiprocessing.Pool(processes=threads, initializer=worker_init) as pool:
            jobs = [
                pool.apply_async(play_game, (
                    engine1_path, engine2_path, idx,
                    depth, time_per_move, clock_time, clock_inc,
                    random_plies, nnue_path, syzygy_path, book_path, iteration
                ))
                for idx in range(num_games)
            ]

            iterator = enumerate(jobs)
            if HAS_TQDM:
                from tqdm import tqdm
                iterator = enumerate(tqdm(jobs, total=num_games, desc="Gauntlet", unit="game", dynamic_ncols=True))

            for idx, job in iterator:
                result = job.get()
                if result:
                    # Extract match metadata before DB insert
                    e1_outcome = result.pop("_e1_outcome")
                    e1_color = result.pop("_e1_color")

                    if e1_outcome == "win":
                        e1_wins += 1
                    elif e1_outcome == "loss":
                        e1_losses += 1
                    elif e1_outcome == "draw":
                        e1_draws += 1

                    # Per-game log
                    total = e1_wins + e1_draws + e1_losses
                    outcome_str = {"win": "WON", "loss": "LOST", "draw": "DRAW"}.get(e1_outcome, "???")
                    score_pct = (e1_wins + 0.5 * e1_draws) / total * 100 if total else 0
                    logger.info(
                        f"Game {total}: {e1_name} ({e1_color}) vs {e2_name} — "
                        f"{result['result']} [{outcome_str}]  "
                        f"Score: {e1_wins}W {e1_draws}D {e1_losses}L ({score_pct:.0f}%)"
                    )

                    if not no_db:
                        batch.append(result)
                    completed += 1
                    if not no_db and len(batch) >= batch_size:
                        try:
                            db.bulk_insert_mappings(MasterGame, batch)
                            db.commit()
                            batch.clear()
                        except Exception as exc:
                            db.rollback()
                            logger.error(f"DB insert failed: {exc}")

            if not no_db and batch:
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
        if db:
            db.close()

    elapsed = time.time() - start_time
    rate = completed / elapsed if elapsed > 0 else 0
    total = e1_wins + e1_draws + e1_losses

    # Final summary
    print("\n" + "=" * 60)
    print(f"  GAUNTLET RESULTS: {e1_name} vs {e2_name}")
    print(f"  Time control: {tc_desc}")
    print("=" * 60)
    if total > 0:
        score_pct = (e1_wins + 0.5 * e1_draws) / total * 100
        print(f"  {e1_name}:  +{e1_wins}  ={e1_draws}  -{e1_losses}  ({score_pct:.1f}%)")
        print(f"  {e2_name}:  +{e1_losses}  ={e1_draws}  -{e1_wins}  ({100 - score_pct:.1f}%)")
        print(f"  Elo difference: {_elo_diff(e1_wins, e1_draws, e1_losses)} (from {e1_name}'s perspective)")
    else:
        print("  No games completed.")
    print(f"  Games: {completed}/{num_games} in {elapsed:.1f}s ({rate:.2f} games/sec)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play Duchess against an external UCI engine and save games for RL training.")
    parser.add_argument("--engine1", type=str, default="engine/build/duchess_cli", help="Path to Duchess engine binary.")
    parser.add_argument("--engine2", type=str, required=True, help="Path to the opponent UCI engine (e.g. stockfish).")
    parser.add_argument("--games", type=int, default=100, help="Number of games to play.")
    parser.add_argument("--threads", type=int, default=4, help="Number of parallel game workers.")
    parser.add_argument("--depth", type=int, default=None, help="Fixed search depth per move.")
    parser.add_argument("--time", type=float, default=5.0, dest="time_per_move", help="Seconds per move (used when --depth and --clock are not set).")
    parser.add_argument("--clock", type=float, default=None, help="Game clock: total seconds per side (e.g. 180 for 3 min). Use with --inc.")
    parser.add_argument("--inc", type=float, default=2.0, help="Clock increment in seconds per move (default: 2).")
    parser.add_argument("--random-plies", type=int, default=8, help="Random opening half-moves for diversity.")
    parser.add_argument("--nnue", type=str, default=None, help="Optional NNUE weights to load in Duchess.")
    parser.add_argument("--syzygy", type=str, default=None, help="Optional Syzygy tablebase directory path.")
    parser.add_argument("--book", type=str, default=None, help="Path to a Polyglot opening book (.bin) for opening diversity.")
    parser.add_argument("--iteration", type=int, default=None, help="The current RL loop iteration (used to tag games in the DB to resume on crash).")
    parser.add_argument("--no-db", action="store_true", help="Skip all database interaction — just play and show the score.")

    args = parser.parse_args()

    # Determine time control
    tc_depth = args.depth
    tc_time_per_move = None
    tc_clock_time = None
    tc_clock_inc = None

    if tc_depth:
        pass # Depth is already set
    elif args.clock:
        tc_clock_time = args.clock
        tc_clock_inc = args.inc
    else:
        tc_time_per_move = args.time_per_move

    for path, label in [(args.engine1, "engine1"), (args.engine2, "engine2")]:
        if not os.path.exists(path):
            logger.error(f"{label} binary not found: {path}")
            sys.exit(1)

    run_gauntlet(
        engine1_path=args.engine1,
        engine2_path=args.engine2,
        num_games=args.games,
        threads=args.threads,
        depth=tc_depth,
        time_per_move=tc_time_per_move,
        clock_time=tc_clock_time,
        clock_inc=tc_clock_inc,
        random_plies=args.random_plies,
        nnue_path=args.nnue,
        syzygy_path=args.syzygy,
        book_path=args.book,
        iteration=args.iteration,
        no_db=args.no_db,
    )
