# Duchess NNUE & Syzygy Guide

This directory contains the training pipeline for the Neural Network Updated Efficiently (NNUE) evaluation function used by Duchess, as well as instructions for enabling perfect endgame play via Syzygy Tablebases.

## Training the NNUE Model

The training pipeline consists of three steps: data generation, model training, and binary export.

### 1. Generate the Dataset
You have two options to generate the positional evaluation dataset required for training:

**Option A: Duchess Self-Play (Recommended)**
Instead of downloading massive human game databases, Duchess can play against herself from randomized starting positions to generate unbiased, high-quality games. These games are automatically saved to your local database.
```bash
# Run 10,000 games of the engine against itself on all CPU cores
python nnue/selfplay.py --games 10000 --depth 4 --random-plies 8
```

**Option B: External Master Games Database**
If you imported a massive PGN file (like Lichess or MegaBase) into your PostgreSQL database using the `Colossal Database Explorer` GUI or `pgn_importer.py` CLI, you can use those human games instead.

Once you have games in your database from either Option A or B, extract the millions of (FEN, Evaluation) pairs:

```bash
# Ensure you are in your Python virtual environment
source ~/.pyenv/versions/duchess/bin/activate 

# Extract evaluations (adjust --games and --depth as needed)
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

To enable perfect endgame evaluation, the engine incorporates the Fathom library. When 5 or fewer pieces remain on the board, the engine will instantly return the exact mate or draw score without needing to calculate further.

1. **Download Tablebases:**
   Download the 3, 4, and 5-piece Syzygy tablebase files to a folder on your computer (6 and 7-piece tablebases are generally too large for standard use). These files have `.rtbw` (for WDL) and `.rtbz` (for DTZ) extensions.
   
2. **Configure via UCI (External GUI):**
   When you start the engine (or configure it in a GUI like Arena/Cutechess/your own GUI), send the following UCI command to tell Duchess where the files are located:

```text
setoption name SyzygyPath value /path/to/your/syzygy/directory
```

3. **Configure via Duchess GUI:**
   The Duchess Python GUI supports explicit multi-file selection for your tablebases. 
   - Open the Duchess application, navigate to the **Syzygy Tablebases** panel in the controls.
   - Click **Select Files (.rtbw/.rtbz)** and choose your 3, 4, and 5-piece files.
   - The GUI will automatically create a managed directory and pass it to the engine via UCI.

Once configured, tablebase probing is automatically integrated directly into the Alpha-Beta search!
