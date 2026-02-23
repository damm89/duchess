#pragma once

#include "board.hpp"
#include <cstdint>

namespace duchess {

uint64_t perft(Board& board, int depth);
void perft_divide(Board& board, int depth);

}  // namespace duchess
