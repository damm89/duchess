# Duchess NNUE & Training Pipeline

This directory contains the full pipeline for training, exporting, and iteratively improving the Neural Network Updated Efficiently (NNUE) evaluation function used by the Duchess C++ engine.

---

## Architecture

The NNUE is a **HalfKP** architecture: `41024 → 256 → 32 → 32 → 1`.

- The Feature Transformer (FT) layer maps each piece's relationship to its king into a 256-dimensional accumulator.
- The accumulator is **incrementally updated** on every `make_move()` call — the full 41 K-input layer is never re-evaluated from scratch.
- The FC layers use `int8` activations and are auto-vectorized by the compiler into SIMD instructions for maximum throughput.
- Weights are **hot-swappable** at runtime via the UCI `NNUEFile` option without restarting the engine.

---

## Pipeline Overview

```
selfplay.py  →  PostgreSQL DB  →  dataset.py  →  train.py  →  export.py  →  duchess.bin
     ↑                                                                            │
     └──────────────── rl_loop.py (orchestrates all steps in a loop) ────────────┘
```

---

## Option 1 — Automated Iterative RL Loop (Recommended)

`rl_loop.py` orchestrates the entire AlphaZero-style self-improvement cycle automatically. Each iteration:

1. Generates self-play games using the **current best network**
2. Extracts (FEN, evaluation) pairs into a `.jsonl` dataset
3. Trains a new PyTorch model with MSE loss
4. Exports the model weights to a C++ `.bin` file
5. **Loads the new network for the next iteration**

```bash
# Basic: 10 iterations, 5000 games each, 6 threads
python nnue/rl_loop.py --iterations 10 --games-per-iter 5000 --threads 6 --epochs-per-iter 20

# With Syzygy tablebases for perfect endgame quality
python nnue/rl_loop.py --iterations 10 --games-per-iter 5000 --threads 6 \
    --syzygy ~/Desktop/Duchess/Syzygy

# Bootstrap from an existing network (e.g. a previous training run)
python nnue/rl_loop.py --iterations 10 --start-nnue nnue/duchess.bin \
    --games-per-iter 5000 --threads 6
```

The latest trained network is always copied to `nnue/duchess.bin` at the end of each iteration. The Duchess GUI automatically loads this file on startup.

---

## Option 2 — Manual Step-by-Step

### Step 1: Generate Self-Play Games

Duchess plays against herself from randomized openings, saving complete games to your PostgreSQL database. Each game starts with `--random-plies` fully random half-moves to ensure opening diversity.

```bash
# 10,000 games with Syzygy tablebases for perfect endgames
python nnue/selfplay.py --games 10000 --threads 6 --depth 4 --random-plies 8 \
    --syzygy ~/Desktop/Duchess/Syzygy

# Or without tablebases
python nnue/selfplay.py --games 10000 --threads 6 --depth 4 --random-plies 8

# Bootstrap from a specific NNUE network
python nnue/selfplay.py --games 10000 --threads 6 --nnue nnue/duchess.bin
```

> [!NOTE]
> A "ply" is one half-move. `--random-plies 8` = 4 full random moves before the engine takes over, creating rich opening diversity. Worker crashes (e.g. illegal moves) are caught and the game is discarded automatically.

### Step 2: Extract Dataset

Fetches games from the database and asks the engine to statically evaluate each position at a given depth, producing a JSONL training file.

```bash
python nnue/dataset.py --games 50000 --out nnue/dataset.jsonl --depth 4
```

`dataset.py` is resilient: it skips game-over positions automatically and restarts the engine subprocess if it crashes mid-run.

### Step 3: Train the Model

> [!TIP]
> **Apple Silicon:** PyTorch automatically uses the `mps` Metal GPU backend on M1/M2/M3/M4 chips, providing a large speedup over CPU.

```bash
python nnue/train.py --data nnue/dataset.jsonl --out nnue/duchess_nnue.pt --epochs 20
```

### Step 4: Export to C++ Binary

Quantizes the PyTorch float weights into `int16` (FT) and `int8` (FC layers) and serializes them into a flat binary format the engine can mmap-load at startup.

```bash
python nnue/export.py nnue/duchess_nnue.pt nnue/duchess_nnue.bin
```

---

## Hot-Swapping the Network

The engine supports loading a different NNUE network at runtime without restart via the `NNUEFile` UCI option:

```text
setoption name NNUEFile value /absolute/path/to/duchess.bin
```

The Duchess Python GUI uses this to auto-load `nnue/duchess.bin` on startup whenever it exists.

---

## Using Syzygy Tablebases During Self-Play

Pass the `--syzygy` flag to `selfplay.py` or `rl_loop.py` with the path to your tablebase directory. Fathom scans the directory recursively for `.rtbw`/`.rtbz` files.

```bash
python nnue/selfplay.py --games 5000 --threads 6 --syzygy ~/Desktop/Duchess/Syzygy
```

With tablebases, the engine plays **provably perfect** moves in positions with ≤5 pieces, resulting in cleaner endgame training data and fewer drawn-out games.

---

## Configuring Syzygy in the GUI / UCI

To enable tablebases for regular play:

- **UCI command:** `setoption name SyzygyPath value /path/to/syzygy/directory`
- **Duchess GUI:** Open the **Syzygy Tablebases** panel in the controls, click **Select Files (.rtbw/.rtbz)**, and the GUI manages a symlink directory automatically.

---

## Generated Files (git-ignored)

The following files are produced by the pipeline and kept local only:

| Pattern | Description |
|---|---|
| `dataset*.jsonl` | Raw (FEN, score) extraction files |
| `duchess_iter_*.pt` | Per-iteration PyTorch model checkpoints |
| `duchess_iter_*.bin` | Per-iteration C++ binary exports |
| `duchess.bin` | **Current best network** — loaded by GUI on startup |
