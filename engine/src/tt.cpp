#include "tt.h"

namespace duchess {

TranspositionTable tt;

TranspositionTable::TranspositionTable() {
    resize(16);  // default 16 MB
}

void TranspositionTable::resize(size_t mb) {
    size_t bytes = mb * 1024 * 1024;
    size_t count = bytes / sizeof(TTEntry);

    // Round down to nearest power of two
    size_t pot = 1;
    while (pot * 2 <= count) pot *= 2;

    table_.assign(pot, TTEntry{});
    mask_ = pot - 1;
}

void TranspositionTable::clear() {
    std::fill(table_.begin(), table_.end(), TTEntry{});
}

bool TranspositionTable::probe(uint64_t key, TTEntry& out) const {
    const TTEntry& entry = table_[key & mask_];
    if (entry.key == key && entry.flag != TT_NONE) {
        out = entry;
        return true;
    }
    return false;
}

void TranspositionTable::store(uint64_t key, int score, int depth, TTFlag flag, uint16_t move) {
    TTEntry& entry = table_[key & mask_];

    // Always-replace if new depth >= stored depth, or entry is empty
    if (entry.key == 0 || depth >= entry.depth) {
        entry.key = key;
        entry.score = static_cast<int16_t>(score);
        entry.move = move;
        entry.depth = static_cast<uint8_t>(depth);
        entry.flag = flag;
    }
}

}  // namespace duchess
