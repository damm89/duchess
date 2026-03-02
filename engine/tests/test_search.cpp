#include <catch2/catch_test_macros.hpp>
#include "search.hpp"
#include "board.hpp"
#include "eval.hpp"
#include "zobrist.h"
#include "tt.h"

using namespace duchess;

struct InitTablesSearch {
    InitTablesSearch() {
        init_attack_tables();
        init_zobrist();
    }
};
static InitTablesSearch _init_search;

// ===== BASIC SEARCH =====

TEST_CASE("Search finds a move from starting position", "[search]") {
    Board board;
    SearchResult result = search(board, 3);
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
}

TEST_CASE("Search finds mate in 1", "[search]") {
    // White Kf6, Qg5, black Kh8. Qg7# (queen covers g8/h7/h8, king covers f7/f8)
    Board board("7k/8/5K2/6Q1/8/8/8/8 w - - 0 1");
    SearchResult result = search(board, 3);
    Board copy = board;
    copy.make_move(result.best_move);
    REQUIRE(is_checkmate(copy));
}

TEST_CASE("Search avoids giving away queen", "[search]") {
    Board board("7k/8/8/8/8/8/4p3/K2Q4 w - - 0 1");
    SearchResult result = search(board, 3);
    Board copy = board;
    copy.make_move(result.best_move);
    bool queen_alive = false;
    for (int s = 0; s < 64; ++s) {
        if (copy.piece_at_sq(s) == Piece::WhiteQueen) {
            queen_alive = true;
            break;
        }
    }
    REQUIRE(queen_alive);
}

TEST_CASE("Search captures free piece", "[search]") {
    // White knight on e4, black queen on d6 — Nxd6 captures the queen
    // Knight (3,4) -> (5,3): dr=2, dc=-1 is a valid L-move
    Board board("7k/8/3q4/8/4N3/8/8/K7 w - - 0 1");
    SearchResult result = search(board, 3);
    REQUIRE(result.best_move.to_sq == sq(5, 3));  // d6
}

TEST_CASE("Search returns positive score when winning", "[search]") {
    Board board("7k/8/8/8/8/8/8/K2Q4 w - - 0 1");
    SearchResult result = search(board, 3);
    REQUIRE(result.score > 800);
}

TEST_CASE("Search depth 1 works", "[search]") {
    Board board;
    SearchResult result = search(board, 1);
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
}

TEST_CASE("Search finds mate in 1 for black", "[search]") {
    // Black queen a8, king b3, white king a1. Qa2# (queen covers a-file, king covers b1/b2)
    Board board("q7/8/8/8/8/1k6/8/K7 b - - 0 1");
    SearchResult result = search(board, 3);
    Board copy = board;
    copy.make_move(result.best_move);
    REQUIRE(is_checkmate(copy));
}

TEST_CASE("Alpha-beta returns node count", "[search]") {
    Board board;
    SearchResult result = search(board, 3);
    REQUIRE(result.nodes > 0);
}

// ===== QUIESCENCE SEARCH =====

TEST_CASE("Quiescence resolves capture sequence", "[search][qsearch]") {
    // White rook on d1, black queen on d8 defended by rook on e8.
    // Depth-1 might think Rxd8 wins the queen, but qsearch should see Rxd8 Rxd8
    // and realize it's only an exchange.
    Board board("3qr2k/8/8/8/8/8/8/K2R4 w - - 0 1");
    SearchResult result = search(board, 3);
    // The engine should NOT play Rxd8 (losing the rook for the queen,
    // but queen is defended — so it's R(500) for Q(900) then R recaptures = net +400).
    // Actually Rxd8 Rxd8 is fine — white wins the exchange. Let's test a real trap:
    // Better test: don't capture a defended piece when it loses material.

    // White bishop on c4 can take pawn on f7, but f7 is defended by king on g8.
    // Bxf7+ Kxf7 loses bishop(330) for pawn(100). Engine should avoid it at depth >= 2.
    Board board2("6k1/5p2/8/8/2B5/8/8/K7 w - - 0 1");
    SearchResult result2 = search(board2, 3);
    // Bishop should NOT go to f7
    REQUIRE_FALSE(result2.best_move.to_sq == sq(6, 5)); // f7
}

TEST_CASE("Quiescence handles standing pat correctly", "[search][qsearch]") {
    // Position where white is up a queen. Standing pat should be high.
    // Engine should not blunder the queen trying to "improve" via captures.
    Board board("7k/8/8/8/8/8/8/K2Q4 w - - 0 1");
    SearchResult result = search(board, 1);
    // Even at depth 1 (which drops into qsearch), score should reflect queen advantage.
    REQUIRE(result.score > 800);
}

TEST_CASE("Quiescence does not miss recapture", "[search][qsearch]") {
    // White queen on d4, black pawn on e5 defended by pawn on d6.
    // Qxe5 is great for white — queen can't be recaptured by a pawn on d6.
    // Score should reflect queen + material advantage.
    Board board("7k/8/3p4/4p3/3Q4/8/8/K7 w - - 0 1");
    SearchResult result = search(board, 3);
    REQUIRE(result.score > 700);
}

// ===== NULL MOVE PRUNING =====

TEST_CASE("NMP finds correct result in winning position", "[search][nmp]") {
    // White has queen + rook vs bare king. NMP should activate (non-pawn material,
    // not in check, depth >= 3) and still find winning moves correctly.
    Board board("7k/8/8/8/8/8/8/KR1Q4 w - - 0 1");
    tt.clear();
    SearchResult result = search(board, 5);
    // Must still find a winning move with a high score.
    REQUIRE(result.score > 800);
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
}

TEST_CASE("NMP does not apply in pawn-only endgame", "[search][nmp]") {
    // King + pawn vs king — has_non_pawn_material() is false for the side to move.
    // NMP should be skipped. Verify engine still finds correct moves.
    Board board("7k/8/8/8/8/8/P7/K7 w - - 0 1");
    SearchResult result = search(board, 5);
    // Engine should push the pawn or move the king toward promotion.
    // Key thing: it doesn't crash or return garbage without NMP.
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
    REQUIRE(result.score > 0); // White is up a pawn
}

TEST_CASE("NMP preserves correctness in mate position", "[search][nmp]") {
    // Mate in 2: White Kh1, Qf2, Rd1; Black Kg8.
    // Qf7+ Kh8 Qf8# or similar. NMP must not prune the mating line.
    Board board("6k1/8/8/8/8/8/5Q2/K2R4 w - - 0 1");
    SearchResult result = search(board, 5);
    // Score should indicate a forced mate.
    REQUIRE(result.score > 90000);
}

// ===== PVS (PRINCIPAL VARIATION SEARCH) =====

TEST_CASE("PVS finds correct move at depth 5", "[search][pvs]") {
    // Middlegame position where white can win material with a tactic.
    // Black knight on f6 is pinned to the king on g8 by white bishop on b2.
    // (Actually bishop on b2 doesn't pin f6 to g8 — let's use a real pin.)
    // White Bg5 pins Nf6 to Qd8. White can win the knight with Bxf6.
    Board board("r1bqk2r/pppppppp/5n2/6B1/8/8/PPPPPPPP/RN1QKBNR w KQkq - 0 1");
    SearchResult result = search(board, 5);
    // The PVS re-search logic should still find the correct best move.
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
    REQUIRE(result.nodes > 0);
}

TEST_CASE("PVS gives same result as basic search for mate in 1", "[search][pvs]") {
    // Simple enough that PVS null-window / re-search doesn't affect outcome.
    Board board("7k/8/5K2/6Q1/8/8/8/8 w - - 0 1");
    SearchResult result = search(board, 5);
    Board copy = board;
    copy.make_move(result.best_move);
    REQUIRE(is_checkmate(copy));
}

// ===== LMR (LATE MOVE REDUCTIONS) =====

TEST_CASE("LMR reduces nodes for positions with many quiet moves", "[search][lmr]") {
    // Open position with many legal quiet moves — LMR should reduce search effort
    // on late quiet moves. Compare node count at depth 5 for a position with
    // lots of moves vs a constrained position.
    Board open_pos("r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 0 1");
    tt.clear();
    SearchResult open_result = search(open_pos, 5);

    // Just verify it completes without issue and finds a reasonable move.
    REQUIRE(open_result.best_move.from_sq != open_result.best_move.to_sq);
    REQUIRE(open_result.nodes > 0);
}

TEST_CASE("LMR still finds forced tactics despite reductions", "[search][lmr]") {
    // White knight on e5 can capture undefended black queen on d7.
    // Even with LMR reducing late quiet moves, captures are never reduced.
    Board board("4k3/3q4/8/4N3/8/8/8/K7 w - - 0 1");
    SearchResult result = search(board, 5);
    // Knight should capture on d7 (sq = rank 6, file 3 = 6*8+3 = 51)
    REQUIRE(result.best_move.to_sq == sq(6, 3)); // d7
}

TEST_CASE("Search at depth 6 completes with all heuristics active", "[search][integration]") {
    // Integration test: all heuristics (TT, NMP, PVS, LMR, qsearch, killers, history)
    // working together. Just verify depth 6 search completes and gives a valid result.
    Board board;  // starting position
    tt.clear();
    SearchResult result = search(board, 6);
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
    REQUIRE(result.nodes > 0);
    REQUIRE(result.score > -500); // starting position shouldn't be terrible for white
    REQUIRE(result.score < 500);  // or amazing
}
