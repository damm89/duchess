#!/usr/bin/env python3
# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""
Stockfish Distillation Dataset Generator.

Annotates positions from a PGN file with a strong engine's evaluations
to produce a high-quality .jsonl training dataset for NNUE.

Usage:
    # From a local PGN file:
    python nnue/distill.py --pgn games.pgn --engine /usr/games/stockfish --out nnue/distill_dataset.jsonl

    # Auto-download the latest Lichess elite PGN:
    python nnue/distill.py --download --pgn /workspace/lichess_elite.pgn --engine /usr/games/stockfish --out nnue/distill_dataset.jsonl
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import multiprocessing
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import chess
import chess.engine
import chess.pgn

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Persistent per-worker engine ---

_engine: Optional[chess.engine.SimpleEngine] = None


def _worker_init(engine_path: str) -> None:
    global _engine
    time.sleep(random.uniform(0, 2.0))  # stagger concurrent startups
    _engine = chess.engine.SimpleEngine.popen_uci(engine_path)


def _annotate_game(args: tuple) -> list[str]:
    """Annotate positions from one PGN game string. Returns list of JSON lines."""
    pgn_str, depth, skip_moves, sample_rate = args
    positions: list[str] = []

    if _engine is None:
        logger.error("Worker engine not initialized — skipping game.")
        return positions

    try:
        game = chess.pgn.read_game(io.StringIO(pgn_str))
        if not game:
            return positions

        result_str = game.headers.get("Result", "*")
        if result_str == "1-0":
            wdl = 1.0
        elif result_str == "0-1":
            wdl = 0.0
        elif result_str == "1/2-1/2":
            wdl = 0.5
        else:
            return positions  # Skip unknown-result games

        board = game.board()
        for move_idx, move in enumerate(game.mainline_moves()):
            board.push(move)

            if move_idx < skip_moves:
                continue
            if board.is_game_over():
                break
            if move_idx % sample_rate != 0:
                continue

            info = _engine.analyse(board, chess.engine.Limit(depth=depth))
            score = info["score"].white()

            if score.is_mate():
                continue

            cp = score.score()
            positions.append(json.dumps({"fen": board.fen(), "score": cp, "wdl": wdl}))

    except Exception as exc:
        logger.debug(f"Game annotation error: {exc}")

    return positions


# --- Download helper ---

def _lichess_elite_url(year: int, month: int) -> str:
    return f"https://database.lichess.org/elite/lichess_elite_{year:04d}-{month:02d}.pgn.zst"


def download_lichess_elite(dest_path: str) -> bool:
    """Download the latest available Lichess elite monthly PGN to dest_path."""
    try:
        import requests
        import zstandard
    except ImportError as e:
        logger.error(f"Missing dependency for download: {e}. Run: pip install requests zstandard")
        return False

    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

    # Try current month, then fall back up to 3 months (file may not be published yet)
    now = datetime.utcnow()
    for months_back in range(4):
        dt = now - timedelta(days=30 * months_back)
        url = _lichess_elite_url(dt.year, dt.month)
        logger.info(f"Trying: {url}")
        try:
            r = requests.head(url, timeout=10)
            if r.status_code == 200:
                break
        except Exception:
            continue
    else:
        logger.error("Could not find a recent Lichess elite PGN to download.")
        return False

    logger.info(f"Downloading {url} → {dest_path} ...")
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))

        dctx = zstandard.ZstdDecompressor()
        # Progress tracks compressed bytes from the socket (matches content-length)
        progress = tqdm(total=total or None, unit="B", unit_scale=True, desc="Downloading") if HAS_TQDM else None
        compressed_read = 0

        with open(dest_path, "wb") as out_f:
            with dctx.stream_reader(r.raw) as reader:
                while True:
                    chunk = reader.read(1 << 20)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    # Approximate compressed progress via raw socket position
                    new_pos = r.raw.tell() if hasattr(r.raw, "tell") else 0
                    if progress and new_pos > compressed_read:
                        progress.update(new_pos - compressed_read)
                        compressed_read = new_pos

        if progress:
            progress.close()

        logger.info(f"Download complete: {dest_path}")
        return True

    except Exception as exc:
        logger.error(f"Download failed: {exc}")
        return False


# --- Main ---

def distill(
    pgn_path: str,
    engine_path: str,
    out_path: str,
    max_games: int,
    depth: int,
    workers: int,
    skip_moves: int,
    sample_rate: int,
) -> int:
    """Annotate up to max_games from pgn_path and write .jsonl to out_path. Returns position count."""
    logger.info(f"Reading PGN: {pgn_path}")
    pgn_strings: list[str] = []
    with open(pgn_path, encoding="utf-8", errors="replace") as f:
        while len(pgn_strings) < max_games:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
            pgn_strings.append(game.accept(exporter))

    logger.info(f"Loaded {len(pgn_strings)} games. Annotating with {workers} workers at depth {depth}...")

    job_args = [(s, depth, skip_moves, sample_rate) for s in pgn_strings]
    total_positions = 0

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as out_f:
        with multiprocessing.Pool(
            processes=workers,
            initializer=_worker_init,
            initargs=(engine_path,),
        ) as pool:
            iterator = pool.imap_unordered(_annotate_game, job_args)
            if HAS_TQDM:
                iterator = tqdm(iterator, total=len(job_args), desc="Distilling", unit="game")
            for lines in iterator:
                for line in lines:
                    out_f.write(line + "\n")
                    total_positions += 1

    logger.info(f"Done. Wrote {total_positions:,} positions to {out_path}")
    return total_positions


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate PGN positions with a strong engine for NNUE distillation.")
    parser.add_argument("--pgn", required=True, help="Path to input PGN file (created by --download if missing).")
    parser.add_argument("--engine", required=True, help="Path to UCI engine (e.g. Stockfish).")
    parser.add_argument("--out", required=True, help="Output .jsonl file path.")
    parser.add_argument("--games", type=int, default=10000, help="Max games to annotate (default: 10000).")
    parser.add_argument("--depth", type=int, default=12, help="Evaluation depth per position (default: 12).")
    parser.add_argument("--workers", type=int, default=4, help="Parallel engine instances (default: 4).")
    parser.add_argument("--skip-moves", type=int, default=10, help="Skip first N half-moves per game (default: 10).")
    parser.add_argument("--sample-rate", type=int, default=3, help="Sample 1-in-N positions per game (default: 3).")
    parser.add_argument("--download", action="store_true", help="Download the latest Lichess elite PGN if --pgn file does not exist.")
    args = parser.parse_args()

    if not os.path.exists(args.pgn):
        if args.download:
            if not download_lichess_elite(args.pgn):
                sys.exit(1)
        else:
            logger.error(f"PGN file not found: {args.pgn}. Use --download to fetch one automatically.")
            sys.exit(1)

    if not os.path.exists(args.engine):
        logger.error(f"Engine not found: {args.engine}")
        sys.exit(1)

    distill(
        pgn_path=args.pgn,
        engine_path=args.engine,
        out_path=args.out,
        max_games=args.games,
        depth=args.depth,
        workers=args.workers,
        skip_moves=args.skip_moves,
        sample_rate=args.sample_rate,
    )


if __name__ == "__main__":
    main()
