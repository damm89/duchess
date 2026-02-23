import argparse
import io
import json
import logging
import random
import os

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

def generate_dataset(output_file: str, max_games: int, engine_path: str, depth: int = 4):
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

    logging.info(f"Loaded {len(games)} games from DB. Starting engine {engine_path} at depth {depth}...")
    
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        logging.error(f"Failed to start engine: {e}")
        return

    extracted_positions = 0

    def start_engine():
        eng = chess.engine.SimpleEngine.popen_uci(engine_path)
        return eng

    engine = start_engine()

    with open(output_file, "w", encoding="utf-8") as f:
        for idx, row in enumerate(games):
            if idx % 100 == 0:
                logging.info(f"Processed {idx}/{len(games)} games... ({extracted_positions} positions extracted)")
                
            pgn_str = io.StringIO(row.move_text)
            game = chess.pgn.read_game(pgn_str)
            if not game:
                continue
                
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
                
                # Never analyse game-over positions — the engine returns (none) or crashes
                if board.is_game_over():
                    break
                    
                # Extract roughly 1 in every 5 positions to avoid heavy correlation
                if move_idx % 5 == 0:
                    try:
                        info = engine.analyse(board, chess.engine.Limit(depth=depth))
                        score = info["score"].white()
                        
                        # We skip forced mates for simple evaluations right now
                        if score.is_mate():
                            continue
                            
                        centipawns = score.score()
                        
                        f.write(json.dumps({
                            "fen": board.fen(),
                            "score": centipawns,
                            "wdl": wdl
                        }) + "\n")
                        extracted_positions += 1
                    except (chess.engine.EngineError, chess.engine.EngineTerminatedError) as e:
                        logging.warning(f"Engine error on position {board.fen()}: {e}. Restarting engine...")
                        try:
                            engine.quit()
                        except Exception:
                            pass
                        engine = start_engine()
                        continue
                    
    try:
        engine.quit()
    except Exception:
        pass
    logging.info(f"Finished dataset generation. Saved {extracted_positions} positions to {output_file}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate NNUE training dataset from MasterGame DB.")
    parser.add_argument("--out", type=str, default="nnue/dataset.jsonl", help="Output JSONL dataset file.")
    parser.add_argument("--games", type=int, default=1000, help="Maximum number of games to parse.")
    parser.add_argument("--engine", type=str, default="engine/build/duchess_cli", help="Path to UCI engine.")
    parser.add_argument("--depth", type=int, default=4, help="Search depth for position evaluation.")
    
    args = parser.parse_args()
    generate_dataset(args.out, args.games, args.engine, args.depth)
