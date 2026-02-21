#include <catch2/catch_test_macros.hpp>
#include "bitboard.hpp"

using namespace duchess;

// --- Square/bit conversion ---

TEST_CASE("Square index from row and col", "[bitboard]") {
    REQUIRE(sq(0, 0) == 0);   // a1
    REQUIRE(sq(0, 7) == 7);   // h1
    REQUIRE(sq(7, 0) == 56);  // a8
    REQUIRE(sq(7, 7) == 63);  // h8
    REQUIRE(sq(1, 4) == 12);  // e2
}

TEST_CASE("Row and col from square index", "[bitboard]") {
    REQUIRE(sq_row(0) == 0);
    REQUIRE(sq_col(0) == 0);
    REQUIRE(sq_row(63) == 7);
    REQUIRE(sq_col(63) == 7);
    REQUIRE(sq_row(12) == 1);
    REQUIRE(sq_col(12) == 4);
}

// --- Bit manipulation ---

TEST_CASE("set_bit and test_bit", "[bitboard]") {
    Bitboard bb = 0;
    set_bit(bb, 0);
    REQUIRE(test_bit(bb, 0));
    REQUIRE_FALSE(test_bit(bb, 1));
    set_bit(bb, 63);
    REQUIRE(test_bit(bb, 63));
}

TEST_CASE("clear_bit", "[bitboard]") {
    Bitboard bb = 0;
    set_bit(bb, 10);
    clear_bit(bb, 10);
    REQUIRE_FALSE(test_bit(bb, 10));
}

TEST_CASE("popcount", "[bitboard]") {
    REQUIRE(popcount(0) == 0);
    REQUIRE(popcount(1) == 1);
    REQUIRE(popcount(0xFF) == 8);
    REQUIRE(popcount(~Bitboard(0)) == 64);
}

TEST_CASE("pop_lsb", "[bitboard]") {
    Bitboard bb = 0;
    set_bit(bb, 3);
    set_bit(bb, 10);
    set_bit(bb, 50);

    int first = pop_lsb(bb);
    REQUIRE(first == 3);
    REQUIRE(popcount(bb) == 2);

    int second = pop_lsb(bb);
    REQUIRE(second == 10);

    int third = pop_lsb(bb);
    REQUIRE(third == 50);
    REQUIRE(bb == 0);
}

// --- Precomputed attack tables ---

TEST_CASE("Knight attacks from center (d4)", "[bitboard][attacks]") {
    init_attack_tables();
    int d4 = sq(3, 3);
    Bitboard attacks = KNIGHT_ATTACKS[d4];
    REQUIRE(popcount(attacks) == 8);
    REQUIRE(test_bit(attacks, sq(5, 4)));  // e6
    REQUIRE(test_bit(attacks, sq(5, 2)));  // c6
    REQUIRE(test_bit(attacks, sq(4, 5)));  // f5
    REQUIRE(test_bit(attacks, sq(4, 1)));  // b5
    REQUIRE(test_bit(attacks, sq(1, 4)));  // e2
    REQUIRE(test_bit(attacks, sq(1, 2)));  // c2
    REQUIRE(test_bit(attacks, sq(2, 5)));  // f3
    REQUIRE(test_bit(attacks, sq(2, 1)));  // b3
}

TEST_CASE("Knight attacks from corner (a1)", "[bitboard][attacks]") {
    init_attack_tables();
    Bitboard attacks = KNIGHT_ATTACKS[sq(0, 0)];
    REQUIRE(popcount(attacks) == 2);
    REQUIRE(test_bit(attacks, sq(2, 1)));  // b3
    REQUIRE(test_bit(attacks, sq(1, 2)));  // c2
}

TEST_CASE("King attacks from center", "[bitboard][attacks]") {
    init_attack_tables();
    Bitboard attacks = KING_ATTACKS[sq(3, 3)];
    REQUIRE(popcount(attacks) == 8);
}

TEST_CASE("King attacks from corner", "[bitboard][attacks]") {
    init_attack_tables();
    Bitboard attacks = KING_ATTACKS[sq(0, 0)];
    REQUIRE(popcount(attacks) == 3);
}

TEST_CASE("White pawn attacks", "[bitboard][attacks]") {
    init_attack_tables();
    // e2 pawn attacks d3 and f3
    Bitboard attacks = PAWN_ATTACKS[0][sq(1, 4)];
    REQUIRE(popcount(attacks) == 2);
    REQUIRE(test_bit(attacks, sq(2, 3)));  // d3
    REQUIRE(test_bit(attacks, sq(2, 5)));  // f3
}

TEST_CASE("Black pawn attacks", "[bitboard][attacks]") {
    init_attack_tables();
    // e7 pawn attacks d6 and f6
    Bitboard attacks = PAWN_ATTACKS[1][sq(6, 4)];
    REQUIRE(popcount(attacks) == 2);
    REQUIRE(test_bit(attacks, sq(5, 3)));  // d6
    REQUIRE(test_bit(attacks, sq(5, 5)));  // f6
}

TEST_CASE("Pawn attacks from a-file has 1 attack", "[bitboard][attacks]") {
    init_attack_tables();
    Bitboard attacks = PAWN_ATTACKS[0][sq(1, 0)];  // a2 white pawn
    REQUIRE(popcount(attacks) == 1);
    REQUIRE(test_bit(attacks, sq(2, 1)));  // b3
}

// --- Sliding piece attacks ---

TEST_CASE("Rook attacks on empty board from d4", "[bitboard][sliding]") {
    init_attack_tables();
    Bitboard occupied = 0;
    set_bit(occupied, sq(3, 3));  // rook itself on d4
    Bitboard attacks = rook_attacks(sq(3, 3), occupied);
    REQUIRE(popcount(attacks) == 14);
}

TEST_CASE("Rook attacks blocked by piece", "[bitboard][sliding]") {
    init_attack_tables();
    Bitboard occupied = 0;
    set_bit(occupied, sq(3, 3));  // rook on d4
    set_bit(occupied, sq(3, 5));  // blocker on f4
    Bitboard attacks = rook_attacks(sq(3, 3), occupied);
    // Can reach e4 and f4 (blocker), but not g4/h4
    REQUIRE(test_bit(attacks, sq(3, 4)));  // e4
    REQUIRE(test_bit(attacks, sq(3, 5)));  // f4 (the blocker square)
    REQUIRE_FALSE(test_bit(attacks, sq(3, 6)));  // g4 blocked
}

TEST_CASE("Bishop attacks on empty board from d4", "[bitboard][sliding]") {
    init_attack_tables();
    Bitboard occupied = 0;
    set_bit(occupied, sq(3, 3));
    Bitboard attacks = bishop_attacks(sq(3, 3), occupied);
    REQUIRE(popcount(attacks) == 13);
}

TEST_CASE("Queen attacks on empty board from d4", "[bitboard][sliding]") {
    init_attack_tables();
    Bitboard occupied = 0;
    set_bit(occupied, sq(3, 3));
    Bitboard attacks = queen_attacks(sq(3, 3), occupied);
    REQUIRE(popcount(attacks) == 27);
}
