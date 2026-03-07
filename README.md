# ♛ Duchess — The Ultimate Chess Application

Duchess is a from-scratch chess engine and desktop application aiming for superhuman strength, a polished analytical GUI, and deep data integration. The engine is written in **C++** and communicates via the **UCI protocol**; the GUI is built with **Python / PyQt6**.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  PyQt6 GUI  (duchess/gui/)                      │
│  Board widget · Eval bar · Analysis panel       │
│  Move log · Multi-engine support                │
└────────────────────┬────────────────────────────┘
                     │  stdin / stdout  (UCI)
┌────────────────────▼────────────────────────────┐
│  C++ Engine  (engine/)                          │
│  Board repr · Move gen · Alpha-beta search      │
│  Zobrist hashing · TT · SEE · Aspiration windows│
│  LMR/PVS · NMP · Futility · Singular extensions │
│  Polyglot opening book · NNUE + SIMD eval       │
│  Syzygy tablebase probing (Fathom) · Lazy SMP   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  NNUE Training Pipeline  (nnue/)                │
│  selfplay.py · gauntlet.py · distill.py         │
│  train.py · export.py · match.py                │
│  rl_loop.py (iterative RL orchestrator)         │
└─────────────────────────────────────────────────┘
```

### Key directories

| Path | Description |
|---|---|
| `engine/` | C++ engine — headers in `include/`, sources in `src/`, tests in `tests/` |
| `duchess/` | Python application — board logic, engine wrapper, processors |
| `duchess/gui/` | PyQt6 interface — board widget, eval bar, main window |
| `nnue/` | NNUE training pipeline — self-play, distillation, PyTorch training, C++ export, RL orchestrator |
| `tests/` | Python test suite (pytest + pytest-qt) |
| `assets/` | Icons, piece images, and other static resources |

---

## Current status

### ✅ Completed

| Phase | Description |
|---|---|
| **1.1** UCI Protocol | Engine communicates via standard UCI over stdin/stdout |
| **1.2** Move Generation & Perft | Full legal move generation with perft verification |
| **2.1** Transposition Tables | Zobrist hashing and a hash table to avoid redundant search |
| **2.2** Quiescence Search | Extends search past horizon with capture-only search and standing pat |
| **2.3** Move Ordering | MVV-LVA for captures, killer moves, history heuristic, TT move priority |
| **3.1** Null Move Pruning | Skips branches where opponent's free move still loses; depth-adaptive R |
| **3.2** LMR & PVS | Late move reductions for quiet moves; principal variation search with null/full window re-search |
| **3.3** Aspiration Windows | Narrow search window around previous depth's score; exponential widening on fail |
| **3.4** Check Extensions | Extend search by 1 ply when in check to avoid horizon effect |
| **3.5** Internal Iterative Deepening | Shallow search to find a TT move when none exists (depth >= 6) |
| **3.6** Singular Extensions | Verify TT move is uniquely best via exclusion search; extend if singular |
| **3.7** Reverse Futility Pruning | Return early when static eval is far above beta at shallow depth |
| **3.8** Futility Pruning | Skip quiet moves at shallow depth when static eval + margin can't reach alpha |
| **3.9** Late Move Pruning | Skip late quiet moves entirely at very shallow depths |
| **3.10** SEE (Static Exchange Evaluation) | Accurate capture sequence analysis for move ordering and pruning losing captures |
| **3.11** Countermove Heuristic | Track which move refutes the opponent's last move for better move ordering |
| **3.12** Lazy SMP | Multi-threaded search with shared transposition table; helper threads at staggered depths |
| **4.1** Syzygy Tablebases | Perfect endgame evaluation with up to 5 pieces via Fathom |
| **4.2** NNUE Evaluation | HalfKP architecture (41024→256→128→128→1) with SIMD-accelerated C++ inference; blended 50/50 with classical eval; hot-swappable via `NNUEFile` UCI option ([Guide](nnue/README.md)) |
| **4.4** Classical Evaluation | Passed/doubled/isolated pawns, bishop pair, rook on open files, piece mobility, king safety (pawn shield), game phase tapering (middlegame/endgame PSTs) |
| **4.3** Iterative RL Self-Play | `rl_loop.py` automates full training loop: self-play → gauntlet → dataset → train → export → repeat; supports Polyglot opening books, Syzygy tablebases |
| **5.1** Board Rendering | QGraphicsView/QGraphicsScene with SVG pieces and smooth drag-and-drop |
| **5.2** Analytical Visualizations | Live evaluation bar (centipawn/mate), principal-variation arrows, threat heatmaps |
| **5.3** Multi-Engine Analysis | Load external UCI engines for side-by-side comparison in analysis panel |
| **6.1** Polyglot Opening Book | Default gm2001 book (credit: chess community); GUI supports loading custom `.bin` books |
| **6.2** Colossal PGN Database | Fast importer for massive PGN files; PostgreSQL backend; GUI explorer with filtering ([Guide](PGN_IMPORT.md)) |
| **6.3** Windows Executable | Automated GitHub Actions CI/CD builds a standalone `.exe` on every version tag push |

### 🔧 Next up

- Lichess API game importer (Phase 6.4)
- Smart time management (allocate more time in complex positions)

---

## Roadmap to beating Queen

The current goal is to surpass Queen (the benchmark opponent engine). Progress is tracked via gauntlet matches.

### Search (done)

All standard alpha-beta improvements are implemented: aspiration windows, check extensions, IID, singular extensions, null move pruning, LMR/PVS, reverse futility pruning, futility pruning, late move pruning, SEE-based ordering and capture pruning, countermove heuristic, killer moves, history heuristic.

### Classical Evaluation (done)

Rich handcrafted eval used standalone and blended 50/50 with NNUE: passed/doubled/isolated pawn detection, bishop pair bonus, rook on open/semi-open files, piece mobility (knights, bishops, rooks, queens), king safety via pawn shield, and game phase tapering between separate middlegame and endgame piece-square tables.

### NNUE Training (in progress)

The RL loop (`rl_loop.py`) automates iterative self-play training with Polyglot opening book support, Syzygy tablebases, and gauntlet matches against an external engine. Architecture: HalfKP 41024→256→128→128→1.

Each iteration:
1. **Self-play** — engine plays itself at depth 3 (10,000 games), capturing positions and scores directly via `engine.analyse()` — no re-evaluation pass needed
2. **Gauntlet** — optional match against an external engine (Queen405x64) for diagnostic purposes
3. **Distillation mix** — 500,000 positions streamed from the [Lichess eval DB](https://database.lichess.org/#evals) are mixed into the training set, anchoring label quality with cloud-depth evaluations
4. **Train** — PyTorch training on combined dataset, resuming from the previous checkpoint
5. **Export** — converted to `.bin` for the C++ engine; auto-pushed to GitHub

Training loss per iteration is logged to `training_log.json`. Gauntlet results are tracked in `match_results.json`.

**Current progress vs Queen405x64 (depth 6):**

| Date | Iteration | W | D | L | Score | Elo diff |
|---|---|---|---|---|---|---|
| 2026-03-06 | 14 | 0 | 0 | 10 | 0.0% | — |
| 2026-03-07 | 24 | 2 | 1 | 37 | 6.2% | −470 |

Git storage: only the latest `duchess_iter_N.bin` is kept in the repository (older weights and all `.pt`/`.jsonl` checkpoints are excluded after use).

### Remaining

| Priority | Feature | Expected impact |
|---|---|---|
| High | More RL iterations (24 done, targeting 50) | Network learns from more diverse positions |
| Medium | Smart time management | Better use of clock in timed games |

---

## Implementation roadmap

The full plan is organised into **three pillars** and **six phases**.

### Pillar 1 — The Engine (Superhuman Strength)

| Phase | Goal | Key techniques |
|---|---|---|
| 1 | Foundation & move-gen integrity | UCI refactor, perft suite |
| 2 | Core search upgrades | Transposition tables, quiescence search, move ordering |
| 3 | Advanced heuristics & scalability | NMP, LMR/PVS, aspiration windows, SEE, futility pruning, singular extensions, Lazy SMP |
| 4 | Modern evaluation & endgames | Syzygy tablebases, classical eval (pawn structure, mobility, king safety, phase tapering), NNUE training pipeline (HalfKP 256→128→128→1), SIMD inference, NNUE+classical blend, iterative RL |

### Pillar 2 — The Interface (Professional GUI)

| Phase | Goal | Key features |
|---|---|---|
| 5 | Hardware-accelerated & reactive GUI | QGraphicsScene / OpenGL board, eval bar, PV arrows, threat heatmaps, multi-engine panel |

### Pillar 3 — Data & Ecosystem

| Phase | Goal | Key features |
|---|---|---|
| 6 | Deep data integration & cloud | Polyglot opening book, PGN database (PostgreSQL), repertoire builder, cloud sync API |

---

## Getting started

### Prerequisites

- **Python 3.10+** with PyQt6
- **CMake 3.16+** and a C++17 compiler
- **Git LFS** (for NNUE weights and training data)
- PostgreSQL (optional, for game database features)

### Quick setup (Ubuntu)

```bash
git clone https://github.com/damm89/duchess.git
cd duchess
bash setup_ubuntu.sh
```

This creates a `py-duchess` virtualenv, installs all dependencies, sets up PostgreSQL, and builds the engine.

### Manual setup

```bash
# Create virtualenv
python3 -m venv py-duchess
source py-duchess/bin/activate
pip install -r requirements.txt

# Build the engine
cd engine
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

The resulting `duchess_cli` binary speaks UCI.

### Run the GUI

```bash
source py-duchess/bin/activate
python -m duchess.main
```

### Run tests

```bash
# Python tests
pytest tests/

# C++ engine tests (after building)
cd engine/build && ctest --output-on-failure
```

---

## Credits

**Author:** Daniel Ammeraal

### Third-party libraries and data

| Component | License | Notes |
|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GPL v3 | Python bindings for Qt 6 |
| [python-chess](https://python-chess.readthedocs.io/) | GPL v3 | PGN parsing and self-play game management |
| [SQLAlchemy](https://www.sqlalchemy.org/) | MIT | Database ORM for game storage |
| [Alembic](https://alembic.sqlalchemy.org/) | MIT | Database migration management |
| [PyTorch](https://pytorch.org/) | BSD | NNUE training pipeline |
| [Catch2](https://github.com/catchorg/Catch2) | BSL-1.0 | C++ test framework for engine tests |
| [Fathom](https://github.com/jdart1/Fathom) | MIT | Syzygy tablebase probing library |
| gm2001.bin | Public domain | Polyglot opening book compiled from GM games |
| [Lichess eval DB](https://database.lichess.org/#evals) | CC0 | 362M cloud-depth evaluated positions used for NNUE distillation |

### AI assistance

Parts of this codebase were developed with assistance from [Claude](https://claude.ai) by Anthropic.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
