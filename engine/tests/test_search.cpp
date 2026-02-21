#include <catch2/catch_test_macros.hpp>
#include "search.hpp"
#include "board.hpp"
#include "eval.hpp"

using namespace duchess;

struct InitTablesSearch {
    InitTablesSearch() { init_attack_tables(); }
};
static InitTablesSearch _init_search;

// ===== BASIC SEARCH =====

TEST_CASE("Search finds a move from starting position", "[search]") {
    Board board;
    SearchResult result = search(board, 3);
    REQUIRE(result.best_move.from_sq != result.best_move.to_sq);
}

TEST_CASE("Search finds mate in 1", "[search]") {
    // White queen h1, king b6, black king a8. Qh8# (queen covers rank 8, king covers a7/b7/b8)
    Board board("k7/8/1K6/8/8/8/8/7Q w - - 0 1");
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
