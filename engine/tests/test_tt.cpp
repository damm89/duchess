#include <catch2/catch_test_macros.hpp>
#include "board.hpp"
#include "zobrist.h"
#include "tt.h"

using namespace duchess;

struct InitZobristTest {
    InitZobristTest() {
        init_attack_tables();
        init_zobrist();
    }
};
static InitZobristTest _init_zobrist_test;

// ===== ZOBRIST HASHING =====

TEST_CASE("Incremental hash matches from-scratch computation", "[zobrist]") {
    Board board;
    // Play a few moves
    board.make_move(Move::from_uci("e2e4"));
    board.make_move(Move::from_uci("e7e5"));
    board.make_move(Move::from_uci("g1f3"));
    board.make_move(Move::from_uci("b8c6"));

    uint64_t incremental = board.hash();
    uint64_t from_scratch = compute_zobrist_hash(board);
    REQUIRE(incremental == from_scratch);
}

TEST_CASE("Transposition gives same hash", "[zobrist]") {
    // Reach the same position via two different move orders (no pawn moves to avoid EP differences)
    // Path 1: 1. Nf3 Nc6 2. Nc3 Nf6
    Board board1;
    board1.make_move(Move::from_uci("g1f3"));
    board1.make_move(Move::from_uci("b8c6"));
    board1.make_move(Move::from_uci("b1c3"));
    board1.make_move(Move::from_uci("g8f6"));

    // Path 2: 1. Nc3 Nf6 2. Nf3 Nc6
    Board board2;
    board2.make_move(Move::from_uci("b1c3"));
    board2.make_move(Move::from_uci("g8f6"));
    board2.make_move(Move::from_uci("g1f3"));
    board2.make_move(Move::from_uci("b8c6"));

    REQUIRE(board1.hash() == board2.hash());
}

TEST_CASE("Different positions have different hashes", "[zobrist]") {
    Board board1;
    Board board2("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1");

    REQUIRE(board1.hash() != board2.hash());
}

TEST_CASE("Hash changes after a move", "[zobrist]") {
    Board board;
    uint64_t h1 = board.hash();
    board.make_move(Move::from_uci("e2e4"));
    uint64_t h2 = board.hash();
    REQUIRE(h1 != h2);
}

TEST_CASE("Incremental hash correct after castling", "[zobrist]") {
    // Position where white can castle kingside
    Board board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1");
    board.make_move(Move::from_uci("e1g1"));  // O-O

    uint64_t incremental = board.hash();
    uint64_t from_scratch = compute_zobrist_hash(board);
    REQUIRE(incremental == from_scratch);
}

TEST_CASE("Incremental hash correct after en passant capture", "[zobrist]") {
    // Position where white can capture en passant
    Board board("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3");
    board.make_move(Move::from_uci("f5e6"));  // en passant

    uint64_t incremental = board.hash();
    uint64_t from_scratch = compute_zobrist_hash(board);
    REQUIRE(incremental == from_scratch);
}

TEST_CASE("Incremental hash correct after promotion", "[zobrist]") {
    Board board("8/P7/8/8/8/8/8/4K2k w - - 0 1");
    Move m = Move::from_uci("a7a8q");
    board.make_move(m);

    uint64_t incremental = board.hash();
    uint64_t from_scratch = compute_zobrist_hash(board);
    REQUIRE(incremental == from_scratch);
}

// ===== TRANSPOSITION TABLE =====

TEST_CASE("TT store and probe", "[tt]") {
    TranspositionTable table;
    table.resize(1);  // 1 MB

    uint64_t key = 0x123456789ABCDEF0ULL;
    table.store(key, 42, 5, TT_EXACT, 0x1234);

    TTEntry entry;
    REQUIRE(table.probe(key, entry));
    REQUIRE(entry.score == 42);
    REQUIRE(entry.depth == 5);
    REQUIRE(entry.flag == TT_EXACT);
    REQUIRE(entry.move == 0x1234);
}

TEST_CASE("TT probe returns false for empty slot", "[tt]") {
    TranspositionTable table;
    table.resize(1);

    TTEntry entry;
    REQUIRE_FALSE(table.probe(0xDEADBEEFULL, entry));
}

TEST_CASE("TT clear empties the table", "[tt]") {
    TranspositionTable table;
    table.resize(1);

    uint64_t key = 0xABCDEF0123456789ULL;
    table.store(key, 100, 10, TT_EXACT, 0);

    table.clear();

    TTEntry entry;
    REQUIRE_FALSE(table.probe(key, entry));
}
