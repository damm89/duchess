#pragma once

#include "board.hpp"
#include <atomic>
#include <chrono>
#include <functional>

namespace duchess {

struct SearchResult {
    Move best_move;
    int score = 0;
    int nodes = 0;
    int depth = 0;
};

// Callback invoked after each completed iterative deepening depth.
// Receives the result for that depth and elapsed time in milliseconds.
using InfoCallback = std::function<void(const SearchResult&, int elapsed_ms)>;

// Search the position to the given depth using alpha-beta with quiescence.
SearchResult search(const Board& board, int depth);

// Iterative deepening search with a time limit in milliseconds.
SearchResult search_timed(const Board& board, int time_limit_ms);

// UCI-style iterative deepening search.
// Supports: external atomic stop flag, optional time limit, optional max depth,
// and an info callback called after each completed depth.
SearchResult search_uci(const Board& board,
                        std::atomic<bool>& stop_flag,
                        int time_limit_ms = 0,
                        int max_depth = 64,
                        InfoCallback info_cb = nullptr,
                        int thread_id = 0);

}  // namespace duchess
