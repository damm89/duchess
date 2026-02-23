"""High-performance parser for massive PGN databases.

Reads PGN files sequentially, extracts headers and move text,
and bulk inserts into the PostgreSQL database using SQLAlchemy.
"""
import argparse
import logging
import re
import sys
import time

from sqlalchemy.orm import Session

from duchess.database import SessionLocal
from duchess.models import MasterGame

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Fast regexes for PGN headers
HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*?)"\]')
RESULT_RE = re.compile(r'(1-0|0-1|1/2-1/2|\*)')

BATCH_SIZE = 10000


def parse_and_import(pgn_path: str, max_games: int = 0, db: Session = None, training_use: bool = False):
    """Parse a PGN file linearly and bulk insert into PostgreSQL."""
    logger.info(f"Starting import of {pgn_path}")
    start_time = time.time()
    
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    current_game = {}
    move_lines = []
    
    batch = []
    total_inserted = 0
    in_moves = False

    def _flush_game():
        nonlocal current_game, move_lines
        if not move_lines and not current_game:
            return

        text = " ".join(move_lines).strip()
        
        # Build dict for bulk insert mapping
        game_dict = {
            "event": current_game.get("Event", "?"),
            "date": current_game.get("Date", "?"),
            "white": current_game.get("White", "?"),
            "black": current_game.get("Black", "?"),
            "result": current_game.get("Result", "*"),
            "white_elo": _parse_int(current_game.get("WhiteElo", "0")),
            "black_elo": _parse_int(current_game.get("BlackElo", "0")),
            "eco": current_game.get("ECO", ""),
            "move_text": text,
            "training_use": training_use,
        }
        batch.append(game_dict)
        
        current_game.clear()
        move_lines.clear()

    with open(pgn_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith("["):
                # If we were reading moves and hit a new header, the previous game is done.
                if in_moves:
                    _flush_game()
                    in_moves = False
                    
                    if len(batch) >= BATCH_SIZE:
                        _insert_batch(db, batch)
                        total_inserted += len(batch)
                        batch.clear()
                        logger.info(f"Inserted {total_inserted} games...")

                    if max_games > 0 and total_inserted >= max_games:
                        break

                match = HEADER_RE.match(line)
                if match:
                    key, val = match.groups()
                    current_game[key] = val
            else:
                in_moves = True
                move_lines.append(line)
                
    # Flush the last game
    if in_moves:
        _flush_game()
    if batch:
        _insert_batch(db, batch)
        total_inserted += len(batch)

    if close_db:
        db.close()
    
    elapsed = time.time() - start_time
    logger.info(f"Completed! Inserted {total_inserted} games in {elapsed:.2f}s "
                f"({total_inserted / elapsed:.0f} games/sec)")


def _insert_batch(db: Session, batch: list[dict]):
    """Bulk insert a batch of game dicts into the DB."""
    try:
        db.bulk_insert_mappings(MasterGame, batch)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting batch: {e}")
        raise RuntimeError(f"Database insertion failed: {e}")


def _parse_int(val: str) -> int:
    try:
        return int(val)
    except ValueError:
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk importer for PGN master databases.")
    parser.add_argument("pgn_file", help="Path to the .pgn file")
    parser.add_argument("--max", type=int, default=0, help="Max games to import (0 for all)")
    
    args = parser.parse_args()
    parse_and_import(args.pgn_file, args.max)
