// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "nnue.h"
#include "board.hpp"
#include <fstream>
#include <iostream>
#include <cstring>
#include <algorithm>

namespace duchess {
namespace nnue {

// Global weights loaded from the binary file
alignas(32) int16_t ft_weights[HALFKP_FEATURES][LAYER1_SIZE];
alignas(32) int16_t ft_bias[LAYER1_SIZE];

alignas(32) int8_t  fc1_weights[LAYER2_SIZE][LAYER1_SIZE * 2];
alignas(32) int32_t fc1_bias[LAYER2_SIZE];

alignas(32) int8_t  fc2_weights[LAYER3_SIZE][LAYER2_SIZE];
alignas(32) int32_t fc2_bias[LAYER3_SIZE];

alignas(32) int8_t  out_weights[1][LAYER3_SIZE];
alignas(32) int32_t out_bias[1];

static bool model_loaded = false;

bool load_model(const std::string& filepath) {
    std::ifstream f(filepath, std::ios::binary);
    if (!f.is_open()) return false;

    uint32_t magic;
    f.read(reinterpret_cast<char*>(&magic), 4);
    if (magic != 0x48435544) return false; // "DUCH"

    uint32_t version;
    f.read(reinterpret_cast<char*>(&version), 4);
    if (version != 1) return false;

    f.read(reinterpret_cast<char*>(ft_weights), sizeof(ft_weights));
    f.read(reinterpret_cast<char*>(ft_bias), sizeof(ft_bias));

    f.read(reinterpret_cast<char*>(fc1_weights), sizeof(fc1_weights));
    f.read(reinterpret_cast<char*>(fc1_bias), sizeof(fc1_bias));

    f.read(reinterpret_cast<char*>(fc2_weights), sizeof(fc2_weights));
    f.read(reinterpret_cast<char*>(fc2_bias), sizeof(fc2_bias));

    f.read(reinterpret_cast<char*>(out_weights), sizeof(out_weights));
    f.read(reinterpret_cast<char*>(out_bias), sizeof(out_bias));

    model_loaded = true;
    return true;
}

int get_piece_type(Piece p, Color perspective) {
    // 0: Pawn, 1: Knight, 2: Bishop, 3: Rook, 4: Queen
    int offset = is_white(p) ? 0 : 5;
    if (perspective == Color::Black) {
        offset = is_white(p) ? 5 : 0;
    }

    switch (p) {
        case Piece::WhitePawn:   case Piece::BlackPawn:   return 0 + offset;
        case Piece::WhiteKnight: case Piece::BlackKnight: return 1 + offset;
        case Piece::WhiteBishop: case Piece::BlackBishop: return 2 + offset;
        case Piece::WhiteRook:   case Piece::BlackRook:   return 3 + offset;
        case Piece::WhiteQueen:  case Piece::BlackQueen:  return 4 + offset;
        default: return -1;
    }
}

int make_feature(int king_sq, int piece_type, int piece_sq) {
    return king_sq * 640 + piece_type * 64 + piece_sq;
}

// SIMD optimized feature update logic
void Accumulator::add_feature(int white_feature_idx, int black_feature_idx) {
    const int16_t* w_weights = ft_weights[white_feature_idx];
    const int16_t* b_weights = ft_weights[black_feature_idx];

    // Auto-vectorized or AVX2 explicitly
    for (int i = 0; i < LAYER1_SIZE; ++i) {
        white[i] += w_weights[i];
        black[i] += b_weights[i];
    }
}

void Accumulator::sub_feature(int white_feature_idx, int black_feature_idx) {
    const int16_t* w_weights = ft_weights[white_feature_idx];
    const int16_t* b_weights = ft_weights[black_feature_idx];

    for (int i = 0; i < LAYER1_SIZE; ++i) {
        white[i] -= w_weights[i];
        black[i] -= b_weights[i];
    }
}

void refresh_accumulator(const Board& board, Accumulator& acc) {
    // Start with bias
    std::memcpy(acc.white.data(), ft_bias, sizeof(ft_bias));
    std::memcpy(acc.black.data(), ft_bias, sizeof(ft_bias));

    int w_ksq = ctzll(board.bitboard_of(Piece::WhiteKing));
    int b_ksq = ctzll(board.bitboard_of(Piece::BlackKing));
    
    // In many implementations, the black king square is mirrored (ksq ^ 56) to maintain symmetry, 
    // but our PyTorch implementation did not mirror. We just used it directly.
    // Ensure this exactly matches how we trained it in nnue/train.py!

    Bitboard pieces = board.occupied() & ~(board.bitboard_of(Piece::WhiteKing) | board.bitboard_of(Piece::BlackKing));
    while (pieces) {
        int sq = pop_lsb(pieces);
        Piece p = board.piece_at_sq(sq);

        int w_pt = get_piece_type(p, Color::White);
        int b_pt = get_piece_type(p, Color::Black);

        if (w_pt != -1 && b_pt != -1) {
            acc.add_feature(
                make_feature(w_ksq, w_pt, sq),
                make_feature(b_ksq, b_pt, sq)
            );
        }
    }
}

int evaluate(int side_to_move, const Accumulator& acc) {
    if (!model_loaded) return 0; // Fallback to classic eval or 0 if not loaded

    // The logic:
    // 1. Concatenate perspectives (us, them) and activate (Clamp 0-127) using AVX2.
    // We are converting int16 from FT to int8 for FC inputs.
    alignas(32) int8_t activated[LAYER1_SIZE * 2];
    
    const int16_t* us   = (side_to_move == 0) ? acc.white.data() : acc.black.data();
    const int16_t* them = (side_to_move == 0) ? acc.black.data() : acc.white.data();
    
    // Simple non-SIMD activation for now (preventing segfaults mapping 256i correctly):
    // In production, you'd use _mm256_packs_epi16
    for (int i = 0; i < LAYER1_SIZE; ++i) {
        int16_t u = us[i];
        int16_t t = them[i];
        if (u < 0) u = 0; else if (u > 127) u = 127;
        if (t < 0) t = 0; else if (t > 127) t = 127;
        activated[i] = static_cast<int8_t>(u);
        activated[i + LAYER1_SIZE] = static_cast<int8_t>(t);
    }

    // FC1
    alignas(32) int32_t fc1_out[LAYER2_SIZE];
    for (int i = 0; i < LAYER2_SIZE; ++i) {
        int32_t sum = fc1_bias[i];
        for (int j = 0; j < LAYER1_SIZE * 2; ++j) {
            sum += fc1_weights[i][j] * activated[j];
        }
        // Shift back down since we multiplied two scaled numbers
        sum /= 64; 
        if (sum < 0) sum = 0; else if (sum > 127) sum = 127;
        fc1_out[i] = sum;
    }

    // FC2
    alignas(32) int32_t fc2_out[LAYER3_SIZE];
    for (int i = 0; i < LAYER3_SIZE; ++i) {
        int32_t sum = fc2_bias[i];
        for (int j = 0; j < LAYER2_SIZE; ++j) {
            sum += fc2_weights[i][j] * fc1_out[j];
        }
        sum /= 64;
        if (sum < 0) sum = 0; else if (sum > 127) sum = 127;
        fc2_out[i] = sum;
    }

    // Output
    int32_t score = out_bias[0];
    for (int j = 0; j < LAYER3_SIZE; ++j) {
        score += out_weights[0][j] * fc2_out[j];
    }
    score /= 64;

    return score;
}

} // namespace nnue
} // namespace duchess
