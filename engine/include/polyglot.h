#pragma once

#include "board.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace duchess {

struct BookEntry {
    uint64_t key;
    uint16_t raw_move;
    uint16_t weight;
    uint32_t learn;
};

struct BookMove {
    Move move;
    uint16_t weight;
};

// Compute the Polyglot Zobrist hash for a board position.
uint64_t polyglot_hash(const Board& board);

// Decode a Polyglot raw move into a duchess Move for the given board.
Move polyglot_decode_move(const Board& board, uint16_t raw);

class OpeningBook {
public:
    OpeningBook() = default;

    // Load a .bin polyglot book file. Returns true on success.
    bool load(const std::string& path);

    // Look up all book moves for the given board position.
    std::vector<BookMove> probe(const Board& board) const;

    // Pick a weighted random book move, or return false if none found.
    bool pick_move(const Board& board, Move& out) const;

    bool is_loaded() const { return !entries_.empty(); }

private:
    std::vector<BookEntry> entries_;
};

}  // namespace duchess
