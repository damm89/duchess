import argparse
import io
import json
import logging
import os
import multiprocessing.dummy as mp_dummy
from tqdm import tqdm

import chess
import chess.engine
import chess.pgn
from sqlalchemy.orm import Session

# Add project root to path so we can import duchess modules
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from duchess.database import SessionLocal
from duchess.models import MasterGame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_dataset(output_file: str, max_games: int, engine_path: str, depth: int = 4, nnue_path: str = None):
    logging.info(f"Connecting to database and fetching up to {max_games} games...")
    db: Session = SessionLocal()
    try:
        query = db.query(MasterGame).filter(MasterGame.training_use.is_(True)).limit(max_games)
        games = query.all()
    finally:
        db.close()

    if not games:
        logging.warning("No games found in the database. Run the PGN importer first (Phase 6.2).")
        return

    logging.info(f"Loaded {len(games)} games from DB. Starting engine pool at depth {depth}...")

    def extract_game(row):
        # Start a thread-local engine to prevent lockups
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        if nnue_path and os.path.exists(nnue_path):
            engine.configure({"NNUEFile": nnue_path})
            
        extracted_batch = []
        try:
            pgn_str = io.StringIO(row.move_text)
            game = chess.pgn.read_game(pgn_str)
            if not game:
                return extracted_batch
                
            result_str = row.result
            if result_str == "1-0":
                wdl = 1.0
            elif result_str == "0-1":
                wdl = 0.0
            else:
                wdl = 0.5  # Draw or unknown
                
            board = game.board()
            for move_idx, move in enumerate(game.mainline_moves()):
                board.push(move)
                
                # Skip the opening moves to avoid training on pure theory memorization
                if move_idx < 15:
                    continue
                
                # Never analyse game-over positions — the engine returns "none"
                if board.is_game_over():
                    break
                    
                # Extract roughly 1 in every 5 positions to avoid heavy correlation
                if move_idx % 5 == 0:
                    info = engine.analyse(board, chess.engine.Limit(depth=depth, time=10.0))
                    score = info["score"].white()
                    
                    if score.is_mate():
                        continue
                        
                    centipawns = score.score()
                    extracted_batch.append(json.dumps({
                        "fen": board.fen(),
                        "score": centipawns,
                        "wdl": wdl
                    }) + "\n")
                    
        except Exception as e:
            pass # Ignore engine crashes on bad variation formats
        finally:
            engine.quit()

        return extracted_batch

    with open(output_file, "w", encoding="utf-8") as f:
        threads = max(1, os.cpu_count() - 1)
        with mp_dummy.Pool(threads) as pool:
            with tqdm(total=len(games), desc="Extracting NNUE Dataset") as pbar:
                for batch in pool.imap_unordered(extract_game, games):
                    for json_line in batch:
                        f.write(json_line)
                    pbar.update(1)
                    
    logging.info(f"Finished dataset generation. Saved to {output_file}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate NNUE training dataset from MasterGame DB.")
    parser.add_argument("--out", type=str, default="nnue/dataset.jsonl", help="Output JSONL dataset file.")
    parser.add_argument("--games", type=int, default=1000, help="Maximum number of games to parse.")
    parser.add_argument("--engine", type=str, default="engine/build/duchess_cli", help="Path to UCI engine.")
    parser.add_argument("--depth", type=int, default=4, help="Search depth for position evaluation.")
    parser.add_argument("--nnue", type=str, default=None, help="Path to NNUE file for evaluation.")
    
    args = parser.parse_args()
    generate_dataset(args.out, args.games, args.engine, args.depth, args.nnue)
