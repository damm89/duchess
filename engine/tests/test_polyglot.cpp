#include <catch2/catch_test_macros.hpp>
#include "polyglot.h"
#include "board.hpp"
#include <fstream>
#include <cstdio>
#include <cstring>

using namespace duchess;

// ——— Polyglot Zobrist hash tests ———

TEST_CASE("Polyglot hash of starting position is known constant", "[polyglot][hash]") {
    // The well-known Polyglot hash for the starting position
    Board board;
    uint64_t h = polyglot_hash(board);
    REQUIRE(h == 0x463b96181691fc9cULL);
}

TEST_CASE("Polyglot hash changes after a move", "[polyglot][hash]") {
    Board b1;
    uint64_t h1 = polyglot_hash(b1);

    Board b2;
    b2.make_move(Move::from_uci("e2e4"));
    uint64_t h2 = polyglot_hash(b2);

    REQUIRE(h1 != h2);
}

TEST_CASE("Polyglot hash after 1.e4 matches known value", "[polyglot][hash]") {
    Board b;
    b.make_move(Move::from_uci("e2e4"));
    uint64_t h = polyglot_hash(b);
    // Known Polyglot hash for position after 1.e4
    REQUIRE(h == 0x823c9b50fd114196ULL);
}

TEST_CASE("Polyglot hash after 1.d4 differs from start and 1.e4", "[polyglot][hash]") {
    Board start;
    uint64_t h_start = polyglot_hash(start);

    Board b_e4;
    b_e4.make_move(Move::from_uci("e2e4"));
    uint64_t h_e4 = polyglot_hash(b_e4);

    Board b_d4;
    b_d4.make_move(Move::from_uci("d2d4"));
    uint64_t h_d4 = polyglot_hash(b_d4);

    REQUIRE(h_d4 != h_start);
    REQUIRE(h_d4 != h_e4);
}

TEST_CASE("Polyglot hash after 1.e4 e5 matches known value", "[polyglot][hash]") {
    Board b;
    b.make_move(Move::from_uci("e2e4"));
    b.make_move(Move::from_uci("e7e5"));
    uint64_t h = polyglot_hash(b);
    REQUIRE(h == 0x0844931a6ef4b9a0ULL);
}

// ——— Move decoding tests ———

TEST_CASE("Polyglot decode e2e4 raw move", "[polyglot][move]") {
    Board b;
    // e2e4: from_file=4, from_rank=1, to_file=4, to_rank=3, promo=0
    // raw = (4 << 6) | (1 << 9) | (4 << 0) | (3 << 3) = 256 + 512 + 4 + 24 = 796
    uint16_t raw = (4 << 0) | (3 << 3) | (4 << 6) | (1 << 9);
    Move m = polyglot_decode_move(b, raw);
    REQUIRE(m.from_sq == 12);  // e2 = 1*8+4 = 12
    REQUIRE(m.to_sq == 28);    // e4 = 3*8+4 = 28
    REQUIRE(m.promotion == Piece::None);
}

TEST_CASE("Polyglot decode castling king-side as king to rook", "[polyglot][move]") {
    // FEN with white allowed to castle king-side
    Board b("r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3");
    // King from e1(file=4,rank=0) to h1(file=7,rank=0) in Polyglot encoding
    uint16_t raw = (7 << 0) | (0 << 3) | (4 << 6) | (0 << 9);
    Move m = polyglot_decode_move(b, raw);
    REQUIRE(m.from_sq == 4);   // e1
    REQUIRE(m.to_sq == 6);     // g1 (converted from h1)
}

TEST_CASE("Polyglot decode promotion to queen", "[polyglot][move]") {
    // White pawn on e7 about to promote
    Board b("8/4P3/8/8/8/8/8/4K2k w - - 0 1");
    // e7e8q: from_file=4,from_rank=6,to_file=4,to_rank=7,promo=4(queen)
    uint16_t raw = (4 << 0) | (7 << 3) | (4 << 6) | (6 << 9) | (4 << 12);
    Move m = polyglot_decode_move(b, raw);
    REQUIRE(m.from_sq == 52);  // e7
    REQUIRE(m.to_sq == 60);    // e8
    REQUIRE(m.promotion == Piece::WhiteQueen);
}

// ——— OpeningBook load/probe tests ———

// Helper to write a minimal .bin book to a temp file.
// Each entry: 8 bytes key (big-endian) + 2 bytes move + 2 bytes weight + 4 bytes learn
static void write_be16(uint8_t* p, uint16_t v) {
    p[0] = static_cast<uint8_t>(v >> 8);
    p[1] = static_cast<uint8_t>(v);
}

static void write_be32(uint8_t* p, uint32_t v) {
    p[0] = static_cast<uint8_t>(v >> 24);
    p[1] = static_cast<uint8_t>(v >> 16);
    p[2] = static_cast<uint8_t>(v >> 8);
    p[3] = static_cast<uint8_t>(v);
}

static void write_be64(uint8_t* p, uint64_t v) {
    write_be32(p, static_cast<uint32_t>(v >> 32));
    write_be32(p + 4, static_cast<uint32_t>(v));
}

static std::string write_test_book(uint64_t key, uint16_t raw_move, uint16_t weight) {
    std::string path = "/tmp/duchess_test_book.bin";
    uint8_t entry[16] = {};
    write_be64(entry, key);
    write_be16(entry + 8, raw_move);
    write_be16(entry + 10, weight);
    write_be32(entry + 12, 0);

    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<char*>(entry), 16);
    return path;
}

TEST_CASE("OpeningBook loads valid .bin file", "[polyglot][book]") {
    Board b;
    uint64_t key = polyglot_hash(b);
    // e2e4 raw: from_file=4,from_rank=1,to_file=4,to_rank=3
    uint16_t raw = (4 << 0) | (3 << 3) | (4 << 6) | (1 << 9);
    auto path = write_test_book(key, raw, 100);

    OpeningBook book;
    REQUIRE(book.load(path));
    REQUIRE(book.is_loaded());

    std::remove(path.c_str());
}

TEST_CASE("OpeningBook::probe returns matching moves", "[polyglot][book]") {
    Board b;
    uint64_t key = polyglot_hash(b);
    uint16_t raw_e2e4 = (4 << 0) | (3 << 3) | (4 << 6) | (1 << 9);
    auto path = write_test_book(key, raw_e2e4, 50);

    OpeningBook book;
    book.load(path);

    auto moves = book.probe(b);
    REQUIRE(moves.size() == 1);
    REQUIRE(moves[0].move.from_sq == 12);  // e2
    REQUIRE(moves[0].move.to_sq == 28);    // e4
    REQUIRE(moves[0].weight == 50);

    std::remove(path.c_str());
}

TEST_CASE("OpeningBook::probe returns empty for unknown position", "[polyglot][book]") {
    Board b;
    uint64_t key = polyglot_hash(b);
    uint16_t raw_e2e4 = (4 << 0) | (3 << 3) | (4 << 6) | (1 << 9);
    auto path = write_test_book(key, raw_e2e4, 50);

    OpeningBook book;
    book.load(path);

    // Different position — after 1.e4
    Board b2;
    b2.make_move(Move::from_uci("e2e4"));
    auto moves = book.probe(b2);
    REQUIRE(moves.empty());

    std::remove(path.c_str());
}

TEST_CASE("OpeningBook::pick_move selects from book", "[polyglot][book]") {
    Board b;
    uint64_t key = polyglot_hash(b);
    uint16_t raw_d2d4 = (3 << 0) | (3 << 3) | (3 << 6) | (1 << 9);
    auto path = write_test_book(key, raw_d2d4, 100);

    OpeningBook book;
    book.load(path);

    Move out;
    bool found = book.pick_move(b, out);
    REQUIRE(found);
    REQUIRE(out.from_sq == 11);  // d2
    REQUIRE(out.to_sq == 27);    // d4

    std::remove(path.c_str());
}

TEST_CASE("OpeningBook rejects non-.bin file", "[polyglot][book]") {
    OpeningBook book;
    REQUIRE_FALSE(book.load("/tmp/nonexistent_book.bin"));
    REQUIRE_FALSE(book.is_loaded());
}

TEST_CASE("Unloaded book probe returns empty", "[polyglot][book]") {
    OpeningBook book;
    Board b;
    auto moves = book.probe(b);
    REQUIRE(moves.empty());

    Move out;
    REQUIRE_FALSE(book.pick_move(b, out));
}
