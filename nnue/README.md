# Duchess NNUE & Syzygy Guide

This directory contains the training pipeline for the Neural Network Updated Efficiently (NNUE) evaluation function used by Duchess, as well as instructions for enabling perfect endgame play via Syzygy Tablebases.

## Training the NNUE Model

The training pipeline consists of three steps: data generation, model training, and binary export.

### 1. Generate the Dataset
First, extract millions of chess positions from the PostgreSQL `MasterGame` database. The script runs the `duchess_cli` engine to evaluate each position at a low depth to use as the training target.

```bash
# Ensure you are in your Python virtual environment
source ~/.pyenv/versions/duchess/bin/activate 

# Run the dataset generator (adjust --games and --depth as needed)
python nnue/dataset.py --games 50000 --out nnue/dataset.jsonl --depth 4
```

### 2. Train the Model
Once you have the `dataset.jsonl` file, you can train the `HalfKP` PyTorch architecture using Mean Squared Error (MSE) loss. The resulting model is saved as a PyTorch `.pt` file.

```bash
python nnue/train.py --data nnue/dataset.jsonl --out nnue/duchess_nnue.pt --epochs 20
```

### 3. Export to C++ Binary
The C++ engine cannot read PyTorch `.pt` files directly. This script quantizes the floating-point weights into highly compressed `int16` and `int8` integers and flattens them into a raw binary `.bin` file.

```bash
python nnue/export.py nnue/duchess_nnue.pt nnue/duchess_nnue.bin
```

*Note: Make sure the resulting `duchess_nnue.bin` file is placed in the `nnue/` directory relative to where the engine is executed, so the C++ engine can load it on startup.*

---

## Using Syzygy Tablebases

To enable perfect endgame evaluation, the engine incorporates the Fathom library. When 6 or fewer pieces remain on the board, the engine will instantly return the exact mate or draw score without needing to calculate further.

1. **Download Tablebases:**
   Download the 3, 4, 5, and/or 6-piece Syzygy tablebase files to a folder on your computer. These files have `.rtbw` (for WDL) and `.rtbz` (for DTZ) extensions.
   
2. **Configure via UCI:**
   When you start the engine (or configure it in a GUI like Arena/Cutechess/your own GUI), send the following UCI command to tell Duchess where the files are located:

```text
setoption name SyzygyPath value /path/to/your/syzygy/directory
```

Once configured, tablebase probing is automatically integrated directly into the Alpha-Beta search!
