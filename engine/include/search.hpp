#pragma once

#include "board.hpp"
#include <chrono>

namespace duchess {

struct SearchResult {
    Move best_move;
    int score = 0;
    int nodes = 0;
    int depth = 0;
};

// Search the position to the given depth using alpha-beta with quiescence.
// Returns the best move and score from the side-to-move's perspective.
SearchResult search(const Board& board, int depth);

// Iterative deepening search with a time limit in milliseconds.
// Searches depth 1, 2, 3, ... and returns the best result found
// when time runs out. Aborts mid-search if the deadline is exceeded.
SearchResult search_timed(const Board& board, int time_limit_ms);

}  // namespace duchess
