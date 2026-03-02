#include <catch2/catch_test_macros.hpp>
#include "eval.hpp"
#include "board.hpp"

using namespace duchess;

struct InitTablesEval {
    InitTablesEval() { init_attack_tables(); }
};
static InitTablesEval _init_eval;

// ===== MATERIAL COUNTING =====

TEST_CASE("Starting position is equal material", "[eval]") {
    Board board;
    int score = evaluate(board);
    REQUIRE(score == 0);
}

TEST_CASE("White up a pawn", "[eval]") {
    // Starting position but remove black's e-pawn
    Board board("rnbqkbnr/pppp1ppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    int score = evaluate(board);
    REQUIRE(score > 0);
    REQUIRE(score >= 50);   // at least ~pawn value with mobility/structure variance
    REQUIRE(score <= 250);  // allow for mobility and pawn structure terms
}

TEST_CASE("Black up a queen", "[eval]") {
    // Remove white queen
    Board board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1");
    int score = evaluate(board);
    REQUIRE(score < -800);  // queen is ~900cp
}

TEST_CASE("Material values are correct", "[eval]") {
    // Lone kings + one white pawn
    Board board("7k/8/8/8/8/8/4P3/K7 w - - 0 1");
    int score = evaluate(board);
    REQUIRE(score > 0);  // white has a pawn advantage

    // Lone kings + one white queen
    Board board2("7k/8/8/8/8/8/8/K2Q4 w - - 0 1");
    int score2 = evaluate(board2);
    REQUIRE(score2 > score);  // queen worth more than pawn
}

// ===== GAME OVER DETECTION =====

TEST_CASE("Checkmate detected", "[eval][gameover]") {
    // Scholar's mate position — black is checkmated
    Board board("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4");
    REQUIRE(is_checkmate(board));
    REQUIRE_FALSE(is_stalemate(board));
}

TEST_CASE("Stalemate detected", "[eval][gameover]") {
    // Black king on a8, white queen on b6, white king on c8 — black to move, stalemate
    Board board("k7/8/1Q6/8/8/8/8/2K5 b - - 0 1");
    REQUIRE(is_stalemate(board));
    REQUIRE_FALSE(is_checkmate(board));
}

TEST_CASE("Not checkmate or stalemate in starting position", "[eval][gameover]") {
    Board board;
    REQUIRE_FALSE(is_checkmate(board));
    REQUIRE_FALSE(is_stalemate(board));
}

TEST_CASE("Checkmate eval returns extreme value", "[eval][gameover]") {
    // Black is checkmated, evaluate from white's perspective
    Board board("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4");
    int score = evaluate(board);
    // From side-to-move perspective: black is mated, so score should be very negative
    REQUIRE(score <= -90000);
}
