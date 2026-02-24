#!/usr/bin/env python3
# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""
Hybrid RL Loop — Self-play on Mac, GPU training on a remote desktop.

This script orchestrates the full RL training pipeline across two machines:
  1. Self-play + dataset extraction run LOCALLY (Mac — CPU bound)
  2. Training + export run REMOTELY (Desktop — GPU accelerated via SSH)
  3. The trained .bin is synced back and loaded for the next iteration

Usage:
    python nnue/rl_hybrid.py \
        --remote user@desktop \
        --remote-dir ~/duchess \
        --iterations 10 \
        --games-per-iter 5000 \
        --threads 8 \
        --epochs-per-iter 20
"""
import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = sys.executable


def run_local(name: str, cmd: list[str]) -> bool:
    logger.info(f"==== [LOCAL] {name} ====")
    logger.info(f"Command: {' '.join(cmd)}")
    start = time.time()
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"==== COMPLETED: {name} in {time.time() - start:.1f}s ====\n")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"==== FAILED: {name} (exit {e.returncode}) ====\n")
        return False
    except KeyboardInterrupt:
        logger.warning(f"\n==== ABORTED: {name} ====\n")
        return False


def run_remote(name: str, remote: str, cmd: str) -> bool:
    logger.info(f"==== [REMOTE] {name} ====")
    logger.info(f"SSH: {remote} -> {cmd}")
    start = time.time()
    try:
        subprocess.run(["ssh", remote, cmd], check=True)
        logger.info(f"==== COMPLETED: {name} in {time.time() - start:.1f}s ====\n")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"==== FAILED: {name} (exit {e.returncode}) ====\n")
        return False


def scp_to(local_path: str, remote: str, remote_path: str) -> bool:
    logger.info(f"SCP: {local_path} -> {remote}:{remote_path}")
    try:
        subprocess.run(["scp", local_path, f"{remote}:{remote_path}"], check=True)
        return True
    except subprocess.CalledProcessError:
        logger.error(f"SCP upload failed: {local_path}")
        return False


def scp_from(remote: str, remote_path: str, local_path: str) -> bool:
    logger.info(f"SCP: {remote}:{remote_path} -> {local_path}")
    try:
        subprocess.run(["scp", f"{remote}:{remote_path}", local_path], check=True)
        return True
    except subprocess.CalledProcessError:
        logger.error(f"SCP download failed: {remote_path}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Hybrid RL Loop — Mac self-play + remote GPU training")
    parser.add_argument("--remote", type=str, required=True,
                        help="SSH target for the GPU machine (e.g. user@desktop)")
    parser.add_argument("--remote-dir", type=str, required=True,
                        help="Path to the Duchess project root on the remote machine")
    parser.add_argument("--remote-python", type=str, default="python3",
                        help="Python executable on the remote machine")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--games-per-iter", type=int, default=5000)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--epochs-per-iter", type=int, default=20)
    parser.add_argument("--start-nnue", type=str, default="")
    parser.add_argument("--syzygy", type=str, default="")
    parser.add_argument("--gauntlet-engine", type=str, default="")
    parser.add_argument("--gauntlet-games", type=int, default=50)

    args = parser.parse_args()

    engine_path = str(PROJECT_ROOT / "engine" / "build" / "duchess_cli")
    current_nnue = args.start_nnue
    remote = args.remote
    remote_dir = args.remote_dir.rstrip("/")

    if not os.path.exists(engine_path):
        logger.error(f"Engine not found at {engine_path}.")
        sys.exit(1)

    for i in range(1, args.iterations + 1):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  HYBRID ITERATION {i}/{args.iterations}")
        logger.info(f"{'=' * 60}\n")

        # ── 1. LOCAL: Self-Play ──────────────────────────────────────
        selfplay_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "selfplay.py"),
            "--games", str(args.games_per_iter),
            "--threads", str(args.threads),
            "--engine", engine_path,
        ]
        if current_nnue and os.path.exists(current_nnue):
            selfplay_cmd.extend(["--nnue", current_nnue])
            logger.info(f"Network: {current_nnue}")
        else:
            logger.info("Using classical evaluation (no NNUE).")
        if args.syzygy and os.path.isdir(args.syzygy):
            selfplay_cmd.extend(["--syzygy", args.syzygy])

        if not run_local("Self-Play", selfplay_cmd):
            sys.exit(1)

        # ── 1b. LOCAL: Optional Gauntlet ─────────────────────────────
        if args.gauntlet_engine and os.path.exists(args.gauntlet_engine):
            gauntlet_cmd = [
                PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "gauntlet.py"),
                "--engine1", engine_path,
                "--engine2", args.gauntlet_engine,
                "--games", str(args.gauntlet_games),
                "--threads", str(args.threads),
            ]
            if current_nnue and os.path.exists(current_nnue):
                gauntlet_cmd.extend(["--nnue", current_nnue])
            if args.syzygy and os.path.isdir(args.syzygy):
                gauntlet_cmd.extend(["--syzygy", args.syzygy])
            if not run_local(f"Gauntlet vs {os.path.basename(args.gauntlet_engine)}", gauntlet_cmd):
                logger.warning("Gauntlet failed — continuing.")

        # ── 2. LOCAL: Extract Dataset ────────────────────────────────
        jsonl_name = f"dataset_iter_{i}.jsonl"
        jsonl_path = str(PROJECT_ROOT / "nnue" / jsonl_name)
        dataset_cmd = [
            PYTHON_EXE, str(PROJECT_ROOT / "nnue" / "dataset.py"),
            "--out", jsonl_path,
            "--games", str(args.games_per_iter * 2),
        ]
        if not run_local("Dataset Extraction", dataset_cmd):
            sys.exit(1)

        # ── 3. UPLOAD: Send dataset to remote ────────────────────────
        remote_jsonl = f"{remote_dir}/nnue/{jsonl_name}"
        if not scp_to(jsonl_path, remote, remote_jsonl):
            sys.exit(1)

        # ── 4. REMOTE: Train on GPU ──────────────────────────────────
        pt_name = f"duchess_iter_{i}.pt"
        remote_pt = f"{remote_dir}/nnue/{pt_name}"
        train_cmd = (
            f"cd {remote_dir} && {args.remote_python} nnue/train.py "
            f"--data nnue/{jsonl_name} --out nnue/{pt_name} "
            f"--epochs {args.epochs_per_iter}"
        )
        if not run_remote("GPU Training", remote, train_cmd):
            sys.exit(1)

        # ── 5. REMOTE: Export to binary ──────────────────────────────
        bin_name = f"duchess_iter_{i}.bin"
        remote_bin = f"{remote_dir}/nnue/{bin_name}"
        export_cmd = (
            f"cd {remote_dir} && {args.remote_python} nnue/export.py "
            f"nnue/{pt_name} nnue/{bin_name}"
        )
        if not run_remote("Model Export", remote, export_cmd):
            sys.exit(1)

        # ── 6. DOWNLOAD: Fetch trained .bin back to Mac ──────────────
        local_bin = str(PROJECT_ROOT / "nnue" / bin_name)
        if not scp_from(remote, remote_bin, local_bin):
            sys.exit(1)

        # Copy to standard location so the GUI picks it up
        std_bin = str(PROJECT_ROOT / "nnue" / "duchess.bin")
        try:
            import shutil
            shutil.copy2(local_bin, std_bin)
        except Exception as e:
            logger.warning(f"Failed to copy to {std_bin}: {e}")

        current_nnue = std_bin
        logger.info(f"✅ Iteration {i} complete — new network: {std_bin}")

    logger.info("\n==== HYBRID RL PIPELINE COMPLETE ====")


if __name__ == "__main__":
    main()
