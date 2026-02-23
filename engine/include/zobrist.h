#pragma once

#include "board.hpp"
#include <cstdint>

namespace duchess {

extern uint64_t piece_keys[12][64];
extern uint64_t en_passant_keys[8];
extern uint64_t castling_keys[16];
extern uint64_t side_key;

void init_zobrist();
uint64_t compute_zobrist_hash(const Board& board);

}  // namespace duchess
