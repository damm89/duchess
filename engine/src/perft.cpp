// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "perft.h"
#include <chrono>
#include <iostream>
#include <iomanip>

namespace duchess {

uint64_t perft(Board& board, int depth) {
    if (depth == 0) return 1;

    auto moves = board.generate_legal_moves();

    if (depth == 1) return static_cast<uint64_t>(moves.size());

    uint64_t nodes = 0;
    for (const auto& m : moves) {
        Board copy = board;
        copy.make_move(m);
        nodes += perft(copy, depth - 1);
    }
    return nodes;
}

void perft_divide(Board& board, int depth) {
    auto start = std::chrono::steady_clock::now();

    auto moves = board.generate_legal_moves();
    uint64_t total = 0;

    for (const auto& m : moves) {
        Board copy = board;
        copy.make_move(m);
        uint64_t count = (depth <= 1) ? 1 : perft(copy, depth - 1);
        total += count;
        std::cout << m.to_uci() << ": " << count << std::endl;
    }

    auto end = std::chrono::steady_clock::now();
    auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    std::cout << std::endl;
    std::cout << "Nodes searched: " << total << std::endl;
    std::cout << "Time: " << elapsed_ms << " ms" << std::endl;
    if (elapsed_ms > 0) {
        uint64_t nps = total * 1000 / static_cast<uint64_t>(elapsed_ms);
        std::cout << "NPS: " << nps << std::endl;
    }
}

}  // namespace duchess
