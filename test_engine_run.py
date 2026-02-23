from duchess.engine_wrapper import UCIEngine, get_engine
from duchess.engine import ChessEngine

print("Testing direct engine...")
e = ChessEngine()
print("best move:", e.get_best_move_timed("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 100))

print("Testing worker...")
from duchess.gui.worker import EngineWorker
w = EngineWorker("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 100)
def on_move(m, n):
    print("move", m, "from", n)
w.move_found.connect(on_move)
w.run()

print("Done")
