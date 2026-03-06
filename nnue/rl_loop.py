#!/usr/bin/env python3
# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""
Reinforcement Learning Orchestrator.
Automates the full pipeline:
1. Distillation (optional, one-time): annotate PGN positions with Stockfish
2. Self-Play (generates games into DB using current NNUE)
3. Dataset Generation (extracts latest games to .jsonl; distillation data mixed in)
4. Training (trains a new PyTorch model)
5. Export (converts .pt to .bin)
6. Repeat (loads new .bin into self-play)
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

TRAINING_LOG = Path(__file__).parent / "training_log.json"

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = sys.executable

def detect_resume_iter(nnue_dir: Path, max_check: int = 100) -> tuple[int, str | None]:
    """Scan nnue_dir for the highest completed iteration and return (start_iter, nnue_path).

    A completed iteration has both a .bin and a .pt checkpoint present.
    Returns (1, None) if nothing is found (fresh start).
    """
    for check_iter in range(max_check, 0, -1):
        bin_file = nnue_dir / f"duchess_iter_{check_iter}.bin"
        pt_file = nnue_dir / f"duchess_iter_{check_iter}.pt"
        if bin_file.exists() and pt_file.exists():
            return check_iter + 1, str(bin_file)
    return 1, None


def run_step(name: str, cmd: list[str]) -> bool:
    logger.info(f"==== STARTING STEP: {name} ====")
    logger.info(f"Command: {' '.join(cmd)}")
    
    start = time.time()
    try:
        result = subprocess.run(cmd, check=True)
        elapsed = time.time() - start
        logger.info(f"==== COMPLETED: {name} in {elapsed:.1f}s ====\n")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"==== FAILED: {name} (Exit code {e.returncode}) ====\n")
        return False
    except KeyboardInterrupt:
        logger.warning(f"\n==== ABORTED BY USER: {name} ====\n")
        return False

def main():
    parser = argparse.ArgumentParser(description="Duchess Iterative RL Self-Play Loop")
    parser.add_argument("--iterations", type=int, default=10, help="Number of full RL loops to run.")
    parser.add_argument("--games-per-iter", type=int, default=5000, help="Number of self-play games to generate per iteration.")
    parser.add_argument("--threads", type=int, default=10, help="Number of engine threads for self-play.")
    parser.add_argument("--selfplay-depth", type=int, default=6, help="Fixed search depth for self-play games (default: 6).")
    parser.add_argument("--start-nnue", type=str, default="", help="Optional: Path to an existing .bin network to bootstrap from.")
    parser.add_argument("--start-iter", type=int, default=1, help="Starting iteration number (to resume a previous run).")
    parser.add_argument("--epochs-per-iter", type=int, default=20, help="Number of training epochs per iteration.")
    parser.add_argument("--syzygy", type=str, default="", help="Optional: Path to Syzygy tablebase directory for perfect endgame play during self-play.")
    parser.add_argument("--gauntlet-engine", type=str, default="", help="Optional: Path to an opponent UCI engine. When set, plays extra games vs this engine before each training step.")
    parser.add_argument("--gauntlet-games", type=int, default=50, help="Number of gauntlet games per iteration (used with --gauntlet-engine).")
    parser.add_argument("--gauntlet-threads", type=int, default=4, help="Number of parallel workers for gauntlet (default: 4; keep low to avoid overwhelming the opponent engine).")
    parser.add_argument("--gauntlet-depth", type=int, default=6, help="Fixed search depth for gauntlet games (default: 6; more reliable than time-based limits with external engines).")
    parser.add_argument("--book", type=str, default="", help="Path to a Polyglot opening book (.bin) for opening diversity in self-play and gauntlet.")
    parser.add_argument("--distill-pgn", type=str, default="", help="Optional: PGN file for one-time Stockfish distillation. Use with --stockfish.")
    parser.add_argument("--stockfish", type=str, default="", help="Path to Stockfish (or any strong UCI engine) for distillation.")
    parser.add_argument("--distill-depth", type=int, default=12, help="Evaluation depth for distillation (default: 12).")
    parser.add_argument("--distill-games", type=int, default=10000, help="Max games to annotate for distillation (default: 10000).")
    parser.add_argument("--distill-workers", type=int, default=4, help="Parallel Stockfish instances for distillation (default: 4; increase on high-core machines).")
    parser.add_argument("--distill-download", action="store_true", help="Auto-download the latest Lichess elite PGN if --distill-pgn file does not exist.")

    args = parser.parse_args()
    
    current_nnue = args.start_nnue
    engine_path = str(PROJECT_ROOT / "engine" / "build" / "duchess_cli")

    if not os.path.exists(engine_path):
        logger.error(f"Engine not found at {engine_path}. Please build the C++ engine first.")
        sys.exit(1)

    # Auto-detect resume: if --start-iter not set, check for existing iteration files
    start_iter = args.start_iter
    if start_iter == 1 and not args.start_nnue:
        start_iter, detected_nnue = detect_resume_iter(PROJECT_ROOT / "nnue")
        if detected_nnue:
            current_nnue = detected_nnue
            logger.info(f"Found existing iteration {start_iter - 1} — resuming from iteration {start_iter}")

    # Optional one-time distillation (run before the loop, skip if already done)
    distill_jsonl = str(PROJECT_ROOT / "nnue" / "distill_dataset.jsonl")
    use_distill = False
    if args.stockfish and os.path.exists(args.stockfish) and (args.distill_pgn or args.distill_download):
        if os.path.exists(distill_jsonl):
            logger.info(f"Distillation dataset already exists at {distill_jsonl} — skipping.")
            use_distill = True
        else:
            pgn_arg = args.distill_pgn or distill_jsonl.replace(".jsonl", ".pgn")
            distill_cmd = [
                PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "distill.py"),
                "--pgn", pgn_arg,
                "--engine", args.stockfish,
                "--out", distill_jsonl,
                "--games", str(args.distill_games),
                "--depth", str(args.distill_depth),
                "--workers", str(args.distill_workers),
            ]
            if args.distill_download:
                distill_cmd.append("--download")
            if run_step("Stockfish Distillation", distill_cmd):
                use_distill = True
                # Push distillation dataset immediately so it survives pod restarts
                push_distill_cmd = [
                    "sh", "-c",
                    "git add nnue/distill_dataset.jsonl && git commit -m 'Add Stockfish distillation dataset' && git pull --rebase origin main && git push"
                ]
                if not run_step("Push Distillation Dataset", push_distill_cmd):
                    logger.warning("Failed to push distillation dataset — it will be regenerated on next pod restart.")
            else:
                logger.warning("Distillation failed — continuing without distillation data.")

    for i in range(start_iter, args.iterations + 1):
        logger.info(f"\n=========================================================")
        logger.info(f"               STARTING ITERATION {i}/{args.iterations}")
        logger.info(f"=========================================================\n")
        
        # 1. Self-Play
        selfplay_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "selfplay.py"),
            "--games", str(args.games_per_iter),
            "--threads", str(args.threads),
            "--depth", str(args.selfplay_depth),
            "--engine", engine_path,
            "--iteration", str(i)
        ]
        if current_nnue and os.path.exists(current_nnue):
            selfplay_cmd.extend(["--nnue", current_nnue])
            logger.info(f"Using network weights from: {current_nnue}")
        else:
            logger.info("Using hardcoded classical evaluation.")
        if args.syzygy and os.path.isdir(args.syzygy):
            selfplay_cmd.extend(["--syzygy", args.syzygy])
            logger.info(f"Using Syzygy tablebases from: {args.syzygy}")
        if args.book and os.path.exists(args.book):
            selfplay_cmd.extend(["--book", args.book])
            logger.info(f"Using opening book: {args.book}")
            
        if not run_step("Self-Play Generation", selfplay_cmd):
            sys.exit(1)

        if args.gauntlet_engine and os.path.exists(args.gauntlet_engine):
            gauntlet_cmd = [
                PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "gauntlet.py"),
                "--engine1", engine_path,
                "--engine2", args.gauntlet_engine,
                "--games", str(args.gauntlet_games),
                "--threads", str(args.gauntlet_threads),
                "--depth", str(args.gauntlet_depth),
                "--iteration", str(i)
            ]
            if current_nnue and os.path.exists(current_nnue):
                gauntlet_cmd.extend(["--nnue", current_nnue])
            if args.syzygy and os.path.isdir(args.syzygy):
                gauntlet_cmd.extend(["--syzygy", args.syzygy])
            if args.book and os.path.exists(args.book):
                gauntlet_cmd.extend(["--book", args.book])
            if not run_step(f"Gauntlet vs {os.path.basename(args.gauntlet_engine)}", gauntlet_cmd):
                logger.warning("Gauntlet step failed — continuing without those games.")
            
        # 2. Extract Dataset
        jsonl_path = str(PROJECT_ROOT / "nnue" / f"dataset_iter_{i}.jsonl")
        dataset_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "dataset.py"),
            "--out", jsonl_path,
            "--games", str(args.games_per_iter * 2 + args.gauntlet_games) # Grab self-play + gauntlet games
        ]
        if current_nnue and os.path.exists(current_nnue):
            dataset_cmd.extend(["--nnue", current_nnue])
        if not run_step("Dataset Extraction", dataset_cmd):
            sys.exit(1)

        # Mix in distillation data if available
        if use_distill:
            try:
                with open(distill_jsonl, "r") as df, open(jsonl_path, "a") as sf:
                    shutil.copyfileobj(df, sf)
                logger.info(f"Mixed distillation data from {distill_jsonl} into training dataset.")
            except Exception as e:
                logger.warning(f"Could not mix distillation data: {e}")

        # 3. Train Model (resume from previous iteration's checkpoint if available)
        pt_path = str(PROJECT_ROOT / "nnue" / f"duchess_iter_{i}.pt")
        prev_pt = str(PROJECT_ROOT / "nnue" / f"duchess_iter_{i - 1}.pt")
        train_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "train.py"),
            "--data", jsonl_path,
            "--out", pt_path,
            "--epochs", str(args.epochs_per_iter)
        ]
        if os.path.exists(prev_pt):
            train_cmd.extend(["--resume", prev_pt])
        loss_out = str(PROJECT_ROOT / "nnue" / f"loss_iter_{i}.json")
        train_cmd.extend(["--loss-out", loss_out])
        if not run_step("PyTorch Training", train_cmd):
            sys.exit(1)

        # Log final training loss
        try:
            final_loss = json.loads(Path(loss_out).read_text())["final_loss"]
            history = json.loads(TRAINING_LOG.read_text()) if TRAINING_LOG.exists() else []
            history.append({"iteration": i, "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "final_loss": round(final_loss, 6)})
            TRAINING_LOG.write_text(json.dumps(history, indent=2))
            logger.info(f"Iteration {i} final loss: {final_loss:.6f}")
            Path(loss_out).unlink()
        except Exception as e:
            logger.warning(f"Could not record training loss: {e}")
            
        # 4. Export to C++ Bin
        bin_path = str(PROJECT_ROOT / "nnue" / f"duchess_iter_{i}.bin")
        export_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "export.py"),
            pt_path,
            bin_path
        ]
        if not run_step("Model Export", export_cmd):
            sys.exit(1)
            
        # Optional: Save a copy to the standard path so the GUI can pick it up immediately
        std_bin_path = str(PROJECT_ROOT / "nnue" / "duchess.bin")
        try:
            import shutil
            shutil.copy2(bin_path, std_bin_path)
        except Exception as e:
            logger.warning(f"Could not copy latest .bin to standard path: {e}")
            
        # Update current network for the next iteration!
        current_nnue = std_bin_path
        logger.info(f"Iteration {i} complete! Engine successfully bootstrapped to new network.")
        
        # 6. Push .bin files to GitHub so weights aren't lost if the server dies
        logger.info("Pushing latest Iteration weights to GitHub...")
        push_cmd = [
            "sh", "-c",
            f"git add nnue/duchess_iter_{i}.bin nnue/duchess.bin nnue/training_log.json; git add nnue/distill_dataset.jsonl 2>/dev/null; git commit -m 'Auto-save Iteration {i} NNUE weights' && git pull --rebase origin main && git push"
        ]
        if not run_step("GitHub Auto-Save", push_cmd):
            logger.warning("Failed to push to GitHub. Check SSH keys or internet connection.")
            
    logger.info("\n==== REINFORCEMENT LEARNING PIPELINE COMPLETE ====")

if __name__ == "__main__":
    main()
