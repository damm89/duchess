# Colossal PGN Database Importer

Duchess includes a high-performance PGN (Portable Game Notation) importer designed to bulk-insert millions of master chess games into a local PostgreSQL database. This data powers the GUI's "Colossal Database Explorer" and is required to generate datasets for the Neural Network (NNUE) training pipeline.

## Prerequisites

- PostgreSQL must be installed, configured, and running.
- You will need a large, uncompressed `.pgn` file. Extensive and free master game databases can be downloaded from:
  - [Lichess Database](https://database.lichess.org/)
  - [Caissabase](http://caissabase.co.uk/)
- *Note: If your download is a `.zst` or `.zip` file, you must exact the internal `.pgn` text file before importing.*

## Importing Games

You have two options for importing games into the Duchess database.

### Option 1: Command Line (Recommended)

For massive gigabyte-sized PGN files containing millions of games, the CLI is highly recommended. It allows you to monitor the specific insertion progress and raw games/sec rate in your terminal.

```bash
# Run from the project root
python duchess/pgn_importer.py path/to/your/master_games.pgn
```

You can optionally cap the number of games to import using the `--max` flag:
```bash
python duchess/pgn_importer.py path/to/your/master_games.pgn --max 1000000
```

### Option 2: The Duchess GUI

If you prefer a graphical interface, you can import directly through the application:
1. Start the Duchess GUI (`python -m duchess.main`).
2. Open the **Colossal Database Explorer** from the right control panel.
3. Click the **Import PGN...** button in the top right.
4. Select your `<file>.pgn`. A background worker thread will import the games while keeping the rest of the application responsive.

## What's Next?
Once your database is populated, you can:
- Search, filter, and review historical games natively within the **Colossal Database Explorer**.
- Double-clicking a game in the explorer will automatically replay it on your application board.
- Generate high-quality positional evaluation datasets for NNUE training using `python nnue/dataset.py` (see the [NNUE Guide](nnue/README.md)).
