// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#pragma once

#include "board.hpp"

namespace duchess {

constexpr int PAWN_VALUE   = 100;
constexpr int KNIGHT_VALUE = 320;
constexpr int BISHOP_VALUE = 330;
constexpr int ROOK_VALUE   = 500;
constexpr int QUEEN_VALUE  = 900;

constexpr int MATE_SCORE = 100000;

// Evaluate from the perspective of the side to move.
// Positive = good for side to move, negative = bad.
int evaluate(const Board& board);

bool is_checkmate(const Board& board);
bool is_stalemate(const Board& board);

}  // namespace duchess
