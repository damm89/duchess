// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#pragma once

#include "board.hpp"
#include <cstdint>

namespace duchess {

uint64_t perft(Board& board, int depth);
void perft_divide(Board& board, int depth);

}  // namespace duchess
