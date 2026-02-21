#include "search.hpp"
#include "eval.hpp"
#include <algorithm>
#include <chrono>

namespace duchess {

static constexpr int INF = 999999;
static constexpr int MAX_QSEARCH_DEPTH = 8;
static constexpr int ABORT_CHECK_INTERVAL = 1024;

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;

static int move_score(const Board& board, const Move& m) {
    Piece captured = board.piece_at_sq(m.to_sq);
    if (captured != Piece::None) {
        static const int piece_val[] = {0, 100, 320, 330, 500, 900, 20000,
                                           100, 320, 330, 500, 900, 20000};
        int victim = piece_val[static_cast<int>(captured)];
        Piece attacker = board.piece_at_sq(m.from_sq);
        int atk = piece_val[static_cast<int>(attacker)];
        return 10000 + victim - atk / 100;
    }
    if (m.promotion != Piece::None) return 9000;
    return 0;
}

static void order_moves(const Board& board, std::vector<Move>& moves) {
    std::sort(moves.begin(), moves.end(), [&](const Move& a, const Move& b) {
        return move_score(board, a) > move_score(board, b);
    });
}

struct SearchState {
    int nodes = 0;
    bool aborted = false;
    TimePoint deadline;
    bool has_deadline = false;

    void check_time() {
        if (has_deadline && (nodes % ABORT_CHECK_INTERVAL == 0)) {
            if (Clock::now() >= deadline) {
                aborted = true;
            }
        }
    }
};

static int quiescence(Board& board, int alpha, int beta, int ply, int qdepth, SearchState& state) {
    state.nodes++;
    if (state.has_deadline) state.check_time();
    if (state.aborted) return 0;

    int stand_pat = evaluate(board);

    if (stand_pat <= -MATE_SCORE + 1000) {
        return -MATE_SCORE + ply;
    }

    if (stand_pat >= beta) return beta;
    if (stand_pat > alpha) alpha = stand_pat;

    if (qdepth >= MAX_QSEARCH_DEPTH) return alpha;

    auto moves = board.generate_legal_moves();

    std::vector<Move> captures;
    for (const auto& m : moves) {
        if (board.piece_at_sq(m.to_sq) != Piece::None || m.promotion != Piece::None) {
            captures.push_back(m);
        }
    }
    order_moves(board, captures);

    for (const auto& m : captures) {
        if (state.aborted) return alpha;
        Board copy = board;
        copy.make_move(m);
        int score = -quiescence(copy, -beta, -alpha, ply + 1, qdepth + 1, state);

        if (score >= beta) return beta;
        if (score > alpha) alpha = score;
    }

    return alpha;
}

static int alpha_beta(Board& board, int depth, int alpha, int beta, int ply, SearchState& state) {
    if (depth <= 0) {
        return quiescence(board, alpha, beta, ply, 0, state);
    }

    state.nodes++;
    if (state.has_deadline) state.check_time();
    if (state.aborted) return 0;

    auto moves = board.generate_legal_moves();

    if (moves.empty()) {
        Color enemy = (board.side_to_move() == Color::White) ? Color::Black : Color::White;
        Piece king = (board.side_to_move() == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
        for (int s = 0; s < 64; ++s) {
            if (board.piece_at_sq(s) == king) {
                if (board.is_attacked(s, enemy)) return -MATE_SCORE + ply;
                return 0;  // stalemate
            }
        }
        return 0;
    }

    order_moves(board, moves);

    for (const auto& m : moves) {
        if (state.aborted) return alpha;
        Board copy = board;
        copy.make_move(m);
        int score = -alpha_beta(copy, depth - 1, -beta, -alpha, ply + 1, state);

        if (score >= beta) return beta;
        if (score > alpha) alpha = score;
    }

    return alpha;
}

static SearchResult search_internal(const Board& board, int depth, SearchState& state) {
    SearchResult result;
    result.score = -INF;
    result.depth = depth;

    auto moves = board.generate_legal_moves();
    if (moves.empty()) return result;

    Board board_copy = board;
    order_moves(board_copy, moves);

    int alpha = -INF;
    int beta = INF;

    for (const auto& m : moves) {
        if (state.aborted) break;
        Board copy = board;
        copy.make_move(m);
        int score = -alpha_beta(copy, depth - 1, -beta, -alpha, 1, state);

        if (state.aborted) break;

        if (score > result.score) {
            result.score = score;
            result.best_move = m;
        }
        if (score > alpha) alpha = score;
    }

    result.nodes = state.nodes;
    return result;
}

SearchResult search(const Board& board, int depth) {
    SearchState state;
    return search_internal(board, depth, state);
}

SearchResult search_timed(const Board& board, int time_limit_ms) {
    SearchState state;
    state.has_deadline = true;
    state.deadline = Clock::now() + std::chrono::milliseconds(time_limit_ms);

    SearchResult best;
    best.score = -INF;

    for (int depth = 1; depth <= 64; ++depth) {
        state.nodes = 0;
        state.aborted = false;

        SearchResult result = search_internal(board, depth, state);

        if (state.aborted) {
            // Time ran out mid-search; keep the previous completed depth's result.
            // But if we have no result yet (depth 1 timed out), use whatever we got.
            if (best.score == -INF && result.best_move.to_uci() != "a1a1") {
                best = result;
            }
            break;
        }

        best = result;

        // If we found a mate, no need to search deeper
        if (best.score >= MATE_SCORE - 100 || best.score <= -MATE_SCORE + 100) {
            break;
        }

        // If more than half the time is used, don't start the next depth
        if (Clock::now() + (Clock::now() - (state.deadline - std::chrono::milliseconds(time_limit_ms)))
            >= state.deadline) {
            break;
        }
    }

    return best;
}

}  // namespace duchess
