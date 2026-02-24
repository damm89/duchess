import argparse
import datetime
import logging
import multiprocessing
import os
import random
import sys
import time
from typing import Optional

import chess
import chess.engine
import chess.pgn
from sqlalchemy.orm import Session
from tqdm import tqdm

# Add project root to path so we can import duchess modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from duchess.database import SessionLocal
from duchess.models import MasterGame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def play_game(engine_path: str, depth: int, random_plies: int, nnue_path: Optional[str], syzygy_path: Optional[str] = None) -> Optional[dict]:
    """Play a single game of the engine against itself from a randomized start.
    
    Returns a dict formatted for the MasterGame database model.
    """
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        if nnue_path:
            engine.configure({"NNUEFile": nnue_path})
        if syzygy_path:
            engine.configure({"SyzygyPath": syzygy_path})
    except Exception as e:
        logger.error(f"Worker failed to start engine: {e}")
        return None

    try:
        board = chess.Board()
        game = chess.pgn.Game()
        
        # 1. Randomized Opening phase
        for _ in range(random_plies):
            if board.is_game_over():
                break
            # Pick a completely random legal move
            legal_moves = list(board.legal_moves)
            random_move = random.choice(legal_moves)
            board.push(random_move)

        # Start standard recording from the randomized board state
        game.setup(board)
        game.headers["Event"] = "Duchess Self-Play"
        game.headers["White"] = "Duchess NNUE-Gen"
        game.headers["Black"] = "Duchess NNUE-Gen"
        game.headers["Date"] = time.strftime("%Y.%m.%d")
        
        node = game
        limit = chess.engine.Limit(depth=depth)

        # 2. Self-Play combat loop
        while not board.is_game_over():
            result = engine.play(board, limit)
            if not result.move:
                break
            
            try:
                board.push(result.move)
            except ValueError:
                logger.warning(f"Engine played illegal move {result.move} in fen {board.fen()}")
                engine.quit()
                return None
                
            node = node.add_variation(result.move)

        # 3. Game Conclusion
        game.headers["Result"] = board.result()
        engine.quit()

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        pgn_string = game.accept(exporter)
        
        return {
            "event": game.headers.get("Event"),
            "date": game.headers.get("Date"),
            "white": game.headers.get("White"),
            "black": game.headers.get("Black"),
            "result": game.headers.get("Result"),
            "white_elo": 0,
            "black_elo": 0,
            "eco": game.headers.get("ECO", ""),
            "move_text": pgn_string,
            "training_use": True
        }

    except Exception as e:
        try:
            engine.quit()
        except:
            pass
        logger.error(f"Worker crashed during game: {e}")
        return None

def worker_init():
    """Ignore SIGINT in workers so the master process can handle Ctrl+C gracefully."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def generate_selfplay_dataset(engine_path: str, num_games: int, threads: int, depth: int, random_plies: int, nnue_path: Optional[str] = None, syzygy_path: Optional[str] = None):
    logger.info(f"Starting {threads} worker threads to generate {num_games} self-play games at Depth {depth}")
    logger.info(f"Each game will begin with {random_plies} random plies.")

    start_time = time.time()
    db: Session = SessionLocal()
    
    completed_games = 0
    batch_size = 100
    batch = []

    try:
        with multiprocessing.Pool(processes=threads, initializer=worker_init) as pool:
            # We don't want to load them all into memory at once if num_games is massive,
            # so we use imap_unordered to process and save them in real-time.
            jobs = (pool.apply_async(play_game, (engine_path, depth, random_plies, nnue_path, syzygy_path)) for _ in range(num_games))
            
            with tqdm(total=num_games, desc="Generating Games", unit="game", dynamic_ncols=True) as pbar:
                for job in jobs:
                    result = job.get()
                    pbar.update(1)
                    
                    rate = pbar.format_dict.get("rate")
                    if rate:
                        avg_time = 1.0 / rate
                        eta_seconds = (pbar.total - pbar.n) / rate
                        eta_dt = datetime.datetime.now() + datetime.timedelta(seconds=eta_seconds)
                        pbar.set_postfix_str(f"Avg: {avg_time:.1f}s/game | Finishes: {eta_dt.strftime('%b %d %H:%M:%S')}")
                        
                    if result:
                        batch.append(result)
                        completed_games += 1
                        
                        if len(batch) >= batch_size:
                            try:
                                db.bulk_insert_mappings(MasterGame, batch)
                                db.commit()
                                batch.clear()
                            except Exception as e:
                                db.rollback()
                                pbar.write(f"Failed to insert batch: {e}")
                
                # Insert final remainder
                if batch:
                    try:
                        db.bulk_insert_mappings(MasterGame, batch)
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        pbar.write(f"Failed to insert final batch: {e}")
                    
    except KeyboardInterrupt:
        logger.warning("\nCaught Ctrl+C! Killing workers...")
        pool.terminate()
        pool.join()
        sys.exit(1)
    finally:
        db.close()

    elapsed = time.time() - start_time
    logger.info(f"Self-play complete! Generated {completed_games} total games in {elapsed:.1f}s ({(completed_games/elapsed if elapsed > 0 else 0):.2f} games/sec)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multithreaded Duchess Self-Play Generator.")
    parser.add_argument("--games", type=int, default=1000, help="Number of games to generate.")
    parser.add_argument("--engine", type=str, default="engine/build/duchess_cli", help="Path to UCI engine.")
    parser.add_argument("--threads", type=int, default=multiprocessing.cpu_count() - 1, help="Number of concurrent worker threads.")
    parser.add_argument("--depth", type=int, default=4, help="Fixed search depth for engine moves.")
    parser.add_argument("--random-plies", type=int, default=8, help="Number of completely random initial half-moves to enforce opening diversity.")
    parser.add_argument("--nnue", type=str, default=None, help="Path to absolute starting network architecture if bootstrapping iteratively.")
    parser.add_argument("--syzygy", type=str, default=None, help="Optional path to Syzygy tablebase directory for perfect endgame play.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.engine):
        logger.error(f"Engine binary not found at {args.engine}. Please build it first.")
        sys.exit(1)
        
    generate_selfplay_dataset(args.engine, args.games, args.threads, args.depth, args.random_plies, args.nnue, args.syzygy)
