from duchess.engine_wrapper import UCIEngine

def test_engine_io():
    engine = UCIEngine()
    
    print("Sending position...")
    engine.set_position_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    
    print("Testing get_legal_moves()")
    moves = engine.get_legal_moves()
    print("Legal moves returned:", len(moves))
    
    print("Testing go_movetime(100)...")
    def on_info(info):
        print(info)
        
    best = engine.go_movetime(100, on_info)
    print("Best move:", best)
    
test_engine_io()
