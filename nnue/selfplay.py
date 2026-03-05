import argparse
import datetime
import logging
import os
import random
import sys
import time
import threading
import resource
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# Force file descriptor limits up to handle 126 C++ processes + Syzygy tables
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
from tqdm import tqdm

# Add project root to path so we can import duchess modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from duchess.models import MasterGame
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
from duchess.database import DATABASE_URL

# Create a custom engine for workers with NO connection pooling (NullPool)
# This prevents 126 workers from exhausting PostgreSQL's 100 max_connections
worker_engine = create_engine(DATABASE_URL, poolclass=NullPool)
WorkerSessionLocal = sessionmaker(bind=worker_engine)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

thread_local = threading.local()
game_queue = queue.Queue()

def database_writer_thread(total_games):
    """Background thread that safely batches games into Postgres, preventing 126-thread DB lockups."""
    db: Session = WorkerSessionLocal()
    written = 0
    batch = []
    
    while written < total_games:
        try:
            game = game_queue.get(timeout=10.0)
            if game is None:  # Poison pill
                break
            batch.append(game)
            written += 1
            
            # Commit in batches of 50 or when finished
            if len(batch) >= 50 or written == total_games:
                try:
                    db.bulk_insert_mappings(MasterGame, batch)
                    db.commit()
                    batch.clear()
                except Exception as e:
                    logger.error(f"DB Batch Insert Failed: {e}")
                    db.rollback()
            
            game_queue.task_done()
        except queue.Empty:
            continue
            
    if batch:
        try:
            db.bulk_insert_mappings(MasterGame, batch)
            db.commit()
        except:
            db.rollback()
            
    db.close()

def get_local_engine(engine_path: str, nnue_path: Optional[str], syzygy_path: Optional[str]):
    """Returns a persisted engine instance for the current thread."""
    if not hasattr(thread_local, "engine"):
        # Stagger initialization over 10 seconds to prevent 126 engines from 
        # simultaneously crashing the RunPod Network Drive while loading Syzygy
        time.sleep(random.uniform(0, 10.0))
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        if nnue_path:
            engine.configure({"NNUEFile": nnue_path})
        if syzygy_path:
            engine.configure({"SyzygyPath": syzygy_path})
        thread_local.engine = engine
    return thread_local.engine

def play_game(engine_path: str, depth: int, random_plies: int, nnue_path: Optional[str], syzygy_path: Optional[str] = None, book_path: Optional[str] = None) -> Optional[bool]:
    """Play a single game of the engine against itself from a randomized start.

    Returns True on DB insert success.
    """
    pid = os.getpid()
    try:
        with open("/workspace/worker_crash.log", "a") as f: f.write(f"[PID {pid}] Thread {threading.get_ident()} Starting engine {engine_path}...\n")
        engine = get_local_engine(engine_path, nnue_path, syzygy_path)
    except Exception as e:
        with open("/workspace/worker_crash.log", "a") as f: f.write(f"[PID {pid}] Thread {threading.get_ident()} CRASHED GETTING ENGINE: {e}\n")
        logger.error(f"Worker failed to start engine: {e}")
        return None

    try:
        board = chess.Board()
        game = chess.pgn.Game()
        
        # 1. Opening phase — use book moves if available, else random
        if book_path:
            with chess.polyglot.open_reader(book_path) as reader:
                for _ in range(random_plies):
                    if board.is_game_over():
                        break
                    entries = list(reader.find_all(board))
                    if entries:
                        # Weighted random selection by Polyglot weight
                        moves = [e.move for e in entries]
                        weights = [e.weight for e in entries]
                        board.push(random.choices(moves, weights=weights, k=1)[0])
                    else:
                        break  # out of book
        else:
            for _ in range(random_plies):
                if board.is_game_over():
                    break
                board.push(random.choice(list(board.legal_moves)))

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
                if result.move not in board.legal_moves:
                    logger.warning(f"Engine returned illegal move {result.move} in fen {board.fen()}")
                    engine.quit()
                    return None
                board.push(result.move)
            except ValueError:
                logger.warning(f"Engine played illegal move {result.move} in fen {board.fen()}")
                engine.quit()
                return None
                
            node = node.add_variation(result.move)

        # 3. Game Conclusion
        game.headers["Result"] = board.result()

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        pgn_string = game.accept(exporter)
        
        game_data = {
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
        
        # 4. Push to background writer thread to avoid Postgres deadlock
        game_queue.put(game_data)
        return True

    except Exception as e:
        try:
            if hasattr(thread_local, "engine"):
                thread_local.engine.quit()
        except:
            pass
        if hasattr(thread_local, "engine"):
            del thread_local.engine
        logger.error(f"Worker crashed during game: {e}")
        return None

def play_game_wrapper(args):
    """Unpacks arguments for ThreadPoolExecutor."""
    return play_game(*args)

import random
import time

def generate_selfplay_dataset(engine_path: str, num_games: int, threads: int, depth: int, random_plies: int, nnue_path: Optional[str] = None, syzygy_path: Optional[str] = None, book_path: Optional[str] = None):
    logger.info(f"Starting {threads} worker threads to generate {num_games} self-play games at Depth {depth}")
    logger.info(f"Each game will begin with {random_plies} random plies.")

    start_time = time.time()
    
    # Start the DB writer daemon
    db_thread = threading.Thread(target=database_writer_thread, args=(num_games,), daemon=True)
    db_thread.start()
    
    completed_games = 0

    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # We use ThreadPoolExecutor because multiprocessing forks permanently deadlock on 126-core RunPod containers!
            # Since the C++ engine does the heavy lifting, the Python GIL doesn't bottleneck us here.
            
            # Use a generator map instead of submit() to prevent queueing 5000 heavy futures into RAM at once!
            job_args = [(engine_path, depth, random_plies, nnue_path, syzygy_path, book_path)] * num_games
            results = executor.map(play_game_wrapper, job_args)
            
            with tqdm(total=num_games, desc="Generating Games", unit="game", dynamic_ncols=True) as pbar:
                for result in results:
                    pbar.update(1)
                    
                    rate = pbar.format_dict.get("rate")
                    if rate:
                        avg_time = 1.0 / rate
                        eta_seconds = (pbar.total - pbar.n) / rate
                        eta_dt = datetime.datetime.now() + datetime.timedelta(seconds=eta_seconds)
                        pbar.set_postfix_str(f"Avg: {avg_time:.1f}s/game | Finishes: {eta_dt.strftime('%b %d %H:%M:%S')}")
                        
                    if result:
                        completed_games += 1

    except KeyboardInterrupt:
        logger.warning(f"Self-play interrupted by user! Stopping {threads} workers...")
        game_queue.put(None) # Tell writer to stop
        sys.exit(1)
        
    # Wait for remaining DB writes
    db_thread.join(timeout=15.0)

    elapsed = time.time() - start_time
    logger.info(f"Self-play complete! Generated {completed_games} total games in {elapsed:.1f}s ({(completed_games/elapsed if elapsed > 0 else 0):.2f} games/sec)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multithreaded Duchess Self-Play Generator.")
    parser.add_argument("--games", type=int, default=1000, help="Number of games to generate.")
    parser.add_argument("--engine", type=str, default="engine/build/duchess_cli", help="Path to UCI engine.")
    parser.add_argument("--threads", type=int, default=os.cpu_count() - 1, help="Number of concurrent worker threads.")
    parser.add_argument("--depth", type=int, default=4, help="Fixed search depth for engine moves.")
    parser.add_argument("--random-plies", type=int, default=8, help="Number of completely random initial half-moves to enforce opening diversity.")
    parser.add_argument("--nnue", type=str, default=None, help="Path to absolute starting network architecture if bootstrapping iteratively.")
    parser.add_argument("--syzygy", type=str, default=None, help="Optional path to Syzygy tablebase directory for perfect endgame play.")
    parser.add_argument("--book", type=str, default=None, help="Path to a Polyglot opening book (.bin) for opening diversity.")

    args = parser.parse_args()
    
    if not os.path.exists(args.engine):
        logger.error(f"Engine binary not found at {args.engine}. Please build it first.")
        sys.exit(1)
        
    generate_selfplay_dataset(args.engine, args.games, args.threads, args.depth, args.random_plies, args.nnue, args.syzygy, args.book)
