from duchess.engine_wrapper import UCIEngine, get_engine
from duchess.gui.worker import EngineWorker
from duchess.board import DuchessBoard

def test_engine_singleton_clash():
    # 1. Initialize board
    board = DuchessBoard()
    print("Board legal moves:", len(board.legal_moves))
    
    # 2. Start a worker, which also grabs the engine behind the scenes in ChessEngine if engine is None
    worker = EngineWorker(fen=board.fen(), time_ms=100)
    
    # Simulate worker run which uses ChessEngine() which uses get_engine()
    print("Worker starts...")
    worker.run()
    
    # Simulate board click checking legal moves while worker supposedly runs
    print("Board legal moves again:", len(board.legal_moves))
    
test_engine_singleton_clash()
