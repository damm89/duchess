// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#pragma once

#include <array>
#include <cstdint>
#include <string>

namespace duchess {

enum class Piece : uint8_t;
enum class Color : uint8_t;
class Board;

namespace nnue {

// HalfKP Dimensions
constexpr int HALFKP_FEATURES = 41024;
constexpr int LAYER1_SIZE = 256;
constexpr int LAYER2_SIZE = 128;
constexpr int LAYER3_SIZE = 128;

// The accumulator stores the output of the first layer (Feature Transformer)
// for both the White and Black perspectives.
// We use int16_t because our weights were quantized to int16.
struct Accumulator {
    alignas(32) std::array<int16_t, LAYER1_SIZE> white;
    alignas(32) std::array<int16_t, LAYER1_SIZE> black;

    void init(const Board& board);
    void add_feature(int white_feature_idx, int black_feature_idx);
    void sub_feature(int white_feature_idx, int black_feature_idx);
};

// Loads the trained PyTorch network weights from the binary file.
bool load_model(const std::string& filepath);

// Evaluates the current board state using the provided accumulator.
// Uses AVX2 SIMD instructions to quickly compute the forward pass.
int evaluate(int side_to_move, const Accumulator& acc);

// Helpers to compute feature indices given a board state.
int make_feature(int king_sq, int piece_type, int piece_sq);
int get_piece_type(Piece p, Color perspective);

// Re-computes the accumulator from scratch for a given board.
void refresh_accumulator(const Board& board, Accumulator& acc);

} // namespace nnue
} // namespace duchess
