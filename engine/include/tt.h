// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#pragma once

#include "board.hpp"
#include <cstdint>
#include <vector>

namespace duchess {

enum TTFlag : uint8_t {
    TT_NONE = 0,
    TT_EXACT = 1,
    TT_LOWER_BOUND = 2,   // score >= beta (fail-high)
    TT_UPPER_BOUND = 3,   // score <= alpha (fail-low)
};

struct TTEntry {
    uint64_t key = 0;
    int16_t score = 0;
    uint16_t move = 0;     // encoded Move
    uint8_t depth = 0;
    uint8_t flag = TT_NONE;
};

class TranspositionTable {
public:
    TranspositionTable();

    void resize(size_t mb);
    void clear();

    bool probe(uint64_t key, TTEntry& out) const;
    void store(uint64_t key, int score, int depth, TTFlag flag, uint16_t move);

private:
    std::vector<TTEntry> table_;
    size_t mask_ = 0;  // size - 1, for power-of-two indexing
};

// Global TT instance
extern TranspositionTable tt;

}  // namespace duchess
