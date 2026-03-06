#!/usr/bin/env python3
# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""
Reinforcement Learning Orchestrator.
Automates the full pipeline:
1. Self-Play (generates games into DB using current NNUE)
2. Dataset Generation (extracts latest games to .jsonl)
3. Training (trains a new PyTorch model)
4. Export (converts .pt to .bin)
5. Repeat (loads new .bin into self-play)
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

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
    parser.add_argument("--start-nnue", type=str, default="", help="Optional: Path to an existing .bin network to bootstrap from.")
    parser.add_argument("--start-iter", type=int, default=1, help="Starting iteration number (to resume a previous run).")
    parser.add_argument("--epochs-per-iter", type=int, default=20, help="Number of training epochs per iteration.")
    parser.add_argument("--syzygy", type=str, default="", help="Optional: Path to Syzygy tablebase directory for perfect endgame play during self-play.")
    parser.add_argument("--gauntlet-engine", type=str, default="", help="Optional: Path to an opponent UCI engine. When set, plays extra games vs this engine before each training step.")
    parser.add_argument("--gauntlet-games", type=int, default=50, help="Number of gauntlet games per iteration (used with --gauntlet-engine).")
    parser.add_argument("--book", type=str, default="", help="Path to a Polyglot opening book (.bin) for opening diversity in self-play and gauntlet.")
    
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

    for i in range(start_iter, args.iterations + 1):
        logger.info(f"\n=========================================================")
        logger.info(f"               STARTING ITERATION {i}/{args.iterations}")
        logger.info(f"=========================================================\n")
        
        # 1. Self-Play
        selfplay_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "selfplay.py"),
            "--games", str(args.games_per_iter),
            "--threads", str(args.threads),
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
                "--threads", str(args.threads),
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
        if not run_step("PyTorch Training", train_cmd):
            sys.exit(1)
            
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
            f"git add nnue/duchess_iter_{i}.bin nnue/duchess.bin && git commit -m 'Auto-save Iteration {i} NNUE weights' && git push"
        ]
        if not run_step("GitHub Auto-Save", push_cmd):
            logger.warning("Failed to push to GitHub. Check SSH keys or internet connection.")
            
    logger.info("\n==== REINFORCEMENT LEARNING PIPELINE COMPLETE ====")

if __name__ == "__main__":
    main()
