// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "zobrist.h"

namespace duchess {

uint64_t piece_keys[12][64];
uint64_t en_passant_keys[8];
uint64_t castling_keys[16];
uint64_t side_key;

// Simple xorshift64 PRNG with fixed seed for deterministic hashing
static uint64_t xorshift64(uint64_t& state) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

void init_zobrist() {
    uint64_t state = 0x7A35DE129CF84B61ULL;  // fixed seed

    for (int piece = 0; piece < 12; ++piece) {
        for (int sq = 0; sq < 64; ++sq) {
            piece_keys[piece][sq] = xorshift64(state);
        }
    }
    for (int file = 0; file < 8; ++file) {
        en_passant_keys[file] = xorshift64(state);
    }
    for (int i = 0; i < 16; ++i) {
        castling_keys[i] = xorshift64(state);
    }
    side_key = xorshift64(state);
}

uint64_t compute_zobrist_hash(const Board& board) {
    uint64_t h = 0;

    for (int sq = 0; sq < 64; ++sq) {
        Piece p = board.piece_at_sq(sq);
        if (p != Piece::None) {
            h ^= piece_keys[static_cast<int>(p) - 1][sq];
        }
    }

    if (board.side_to_move() == Color::Black) {
        h ^= side_key;
    }

    h ^= castling_keys[board.castling_rights()];

    int ep = board.en_passant_square();
    if (ep >= 0) {
        h ^= en_passant_keys[ep % 8];  // file of EP square
    }

    return h;
}

}  // namespace duchess
