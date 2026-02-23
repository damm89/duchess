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
│  Zobrist hashing · Transposition tables         │
│  Polyglot opening book · Static eval            │
└─────────────────────────────────────────────────┘
```

### Key directories

| Path | Description |
|---|---|
| `engine/` | C++ engine — headers in `include/`, sources in `src/`, tests in `tests/` |
| `duchess/` | Python application — board logic, engine wrapper, processors |
| `duchess/gui/` | PyQt6 interface — board widget, eval bar, main window |
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
| **3.3** Lazy SMP | Multi-threaded search with shared transposition table; helper threads at staggered depths |
| **5.1** Board Rendering | QGraphicsView/QGraphicsScene with SVG pieces and smooth drag-and-drop |
| **5.2** Analytical Visualizations | Live evaluation bar (centipawn/mate), principal-variation arrows, threat heatmaps |
| **5.3** Multi-Engine Analysis | Load external UCI engines for side-by-side comparison in analysis panel |
| **6.1** Polyglot Opening Book | Default gm2001 book (credit: chess community); GUI supports loading custom `.bin` books |

### 🔧 Next up

- Syzygy tablebase integration (Phase 4.1)
- NNUE evaluation (Phase 4.2 / 4.3)
- PGN database with PostgreSQL (Phase 6.2)
- Cloud sync API (Phase 6.3)

---

## Implementation roadmap

The full plan is organised into **three pillars** and **six phases**.

### Pillar 1 — The Engine (Superhuman Strength)

| Phase | Goal | Key techniques |
|---|---|---|
| 1 | Foundation & move-gen integrity | UCI refactor, perft suite |
| 2 | Core search upgrades | Transposition tables, quiescence search, move ordering |
| 3 | Advanced heuristics & scalability | Null-move pruning, LMR / PVS, Lazy SMP multi-threading |
| 4 | Modern evaluation & endgames | Syzygy tablebases, NNUE training pipeline, SIMD inference |

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
- PostgreSQL (optional, for game database features)

### Build the engine

```bash
cd engine
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

The resulting `duchess_engine` binary speaks UCI.

### Run the GUI

```bash
pip install -r requirements.txt
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

## License

*To be determined.*
