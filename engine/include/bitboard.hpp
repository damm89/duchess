// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#pragma once

#include <cstdint>

#ifdef _MSC_VER
#include <intrin.h>
#endif

namespace duchess {

using Bitboard = uint64_t;

// Square index: 0=a1, 1=b1, ..., 7=h1, 8=a2, ..., 63=h8
// sq = row * 8 + col

inline constexpr int sq(int row, int col) { return row * 8 + col; }
inline constexpr int sq_row(int s) { return s >> 3; }
inline constexpr int sq_col(int s) { return s & 7; }

inline constexpr Bitboard bit(int square) { return Bitboard(1) << square; }
inline constexpr void set_bit(Bitboard& bb, int square) { bb |= bit(square); }
inline constexpr void clear_bit(Bitboard& bb, int square) { bb &= ~bit(square); }
inline constexpr bool test_bit(Bitboard bb, int square) { return (bb >> square) & 1; }

// Cross-platform bit intrinsics
inline int ctzll(uint64_t x) {
#ifdef _MSC_VER
    unsigned long idx;
    _BitScanForward64(&idx, x);
    return static_cast<int>(idx);
#else
    return __builtin_ctzll(x);
#endif
}

inline int popcountll(uint64_t x) {
#ifdef _MSC_VER
    return static_cast<int>(__popcnt64(x));
#else
    return __builtin_popcountll(x);
#endif
}

// Pop least significant bit, return its index
inline int pop_lsb(Bitboard& bb) {
    int idx = ctzll(bb);
    bb &= bb - 1;
    return idx;
}

inline int popcount(Bitboard bb) {
    return popcountll(bb);
}

// Precomputed attack tables
extern Bitboard KNIGHT_ATTACKS[64];
extern Bitboard KING_ATTACKS[64];
extern Bitboard PAWN_ATTACKS[2][64];  // [color][square], 0=white, 1=black

// Sliding piece attacks (classical ray approach)
Bitboard bishop_attacks(int square, Bitboard occupied);
Bitboard rook_attacks(int square, Bitboard occupied);
inline Bitboard queen_attacks(int square, Bitboard occupied) {
    return bishop_attacks(square, occupied) | rook_attacks(square, occupied);
}

// Must be called once at startup
void init_attack_tables();

}  // namespace duchess
