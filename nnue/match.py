#!/usr/bin/env python3
"""Quick standalone match — no DB, no training, just results."""
import argparse
import datetime
import json
import os
import random
import chess
import chess.engine
import chess.pgn
from pathlib import Path
from tqdm import tqdm

RESULTS_FILE = Path(__file__).parent / "match_results.json"


def play_game(args):
    engine1_path, engine2_path, game_index, depth, nnue_path, syzygy_path = args
    duchess_is_white = (game_index % 2 == 0)

    try:
        e1 = chess.engine.SimpleEngine.popen_uci(engine1_path)
        e2 = chess.engine.SimpleEngine.popen_uci(engine2_path)
    except Exception as exc:
        print(f"Engine init failed for game {game_index}: {exc}")
        return "error", 0

    if nnue_path:
        try: e1.configure({"NNUEFile": nnue_path})
        except Exception: pass
    if syzygy_path:
        for e in (e1, e2):
            try: e.configure({"SyzygyPath": syzygy_path})
            except Exception: pass

    board = chess.Board()
    for _ in range(8):
        if board.is_game_over(): break
        board.push(random.choice(list(board.legal_moves)))

    limit = chess.engine.Limit(depth=depth)
    while not board.is_game_over():
        engine = e1 if (board.turn == chess.WHITE) == duchess_is_white else e2
        result = engine.play(board, limit)
        board.push(result.move)

    e1.quit()
    e2.quit()

    result = board.result()
    if result == "1-0":
        outcome = "win" if duchess_is_white else "loss"
    elif result == "0-1":
        outcome = "loss" if duchess_is_white else "win"
    else:
        outcome = "draw"
    return outcome, board.fullmove_number


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine1", default="engine/build/duchess_cli")
    parser.add_argument("--engine2", required=True)
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--threads", type=int, default=10)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--nnue", default=None)
    parser.add_argument("--syzygy", default=None)
    parser.add_argument("--iteration", type=int, default=None, help="RL iteration number to tag this result.")
    args = parser.parse_args()

    e1_name = os.path.basename(args.engine1)
    e2_name = os.path.basename(args.engine2)

    job_args = [(args.engine1, args.engine2, i, args.depth, args.nnue, args.syzygy)
                for i in range(args.games)]

    wins = draws = losses = 0
    move_counts = []
    for job in tqdm(job_args, desc="Match"):
        outcome, moves = play_game(job)
        if outcome == "win":    wins += 1
        elif outcome == "draw": draws += 1
        elif outcome == "loss": losses += 1
        if moves: move_counts.append(moves)

    total = wins + draws + losses
    score = (wins + 0.5 * draws) / total * 100
    avg_moves = sum(move_counts) / len(move_counts) if move_counts else 0
    print(f"\n{'='*50}")
    print(f"  {e1_name} vs {e2_name}  ({args.games} games, depth {args.depth})")
    print(f"  {e1_name}:  +{wins}  ={draws}  -{losses}  ({score:.1f}%)")
    print(f"  {e2_name}:  +{losses}  ={draws}  -{wins}  ({100-score:.1f}%)")
    print(f"  Avg game length: {avg_moves:.0f} moves  (min {min(move_counts)}, max {max(move_counts)})")
    print(f"{'='*50}\n")

    record = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "iteration": args.iteration,
        "opponent": e2_name,
        "depth": args.depth,
        "games": total,
        "wins": wins, "draws": draws, "losses": losses,
        "score_pct": round(score, 1),
        "avg_moves": round(avg_moves, 1),
    }
    history = json.loads(RESULTS_FILE.read_text()) if RESULTS_FILE.exists() else []
    history.append(record)
    RESULTS_FILE.write_text(json.dumps(history, indent=2))
    print(f"Result saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
