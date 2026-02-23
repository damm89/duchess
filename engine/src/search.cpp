// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "search.hpp"
#include "eval.hpp"
#include "tt.h"
#include "tbprobe.h"
#include <algorithm>
#include <chrono>

namespace duchess {

static constexpr int INF = 999999;
static constexpr int MAX_QSEARCH_DEPTH = 8;
static constexpr int ABORT_CHECK_INTERVAL = 1024;
static constexpr int MAX_PLY = 128;

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;

struct SearchState {
    int nodes = 0;
    bool aborted = false;
    TimePoint deadline;
    bool has_deadline = false;
    std::atomic<bool>* stop_flag = nullptr;
    Move killer_moves[MAX_PLY][2] = {};
    int history_table[2][64][64] = {};

    void check_abort() {
        if (nodes % ABORT_CHECK_INTERVAL != 0) return;
        if (has_deadline && Clock::now() >= deadline) {
            aborted = true;
        }
        if (stop_flag && stop_flag->load(std::memory_order_relaxed)) {
            aborted = true;
        }
    }
};

static const int PIECE_VAL[] = {0, 100, 320, 330, 500, 900, 20000,
                                   100, 320, 330, 500, 900, 20000};

static int move_score(const Board& board, const Move& m,
                      uint16_t tt_move, const SearchState* state, int ply) {
    // TT move highest priority
    if (tt_move && m.encode() == tt_move) return 1000000;

    // Captures: MVV-LVA
    Piece captured = board.piece_at_sq(m.to_sq);
    if (captured != Piece::None) {
        int victim = PIECE_VAL[static_cast<int>(captured)];
        Piece attacker = board.piece_at_sq(m.from_sq);
        int atk = PIECE_VAL[static_cast<int>(attacker)];
        return 100000 + victim * 100 - atk;
    }

    // Promotions
    if (m.promotion != Piece::None) return 90000;

    // Killer moves
    if (state && ply >= 0 && ply < MAX_PLY) {
        if (m.from_sq == state->killer_moves[ply][0].from_sq &&
            m.to_sq == state->killer_moves[ply][0].to_sq) return 9000;
        if (m.from_sq == state->killer_moves[ply][1].from_sq &&
            m.to_sq == state->killer_moves[ply][1].to_sq) return 8000;
    }

    // History heuristic
    if (state) {
        int color = static_cast<int>(board.side_to_move());
        return state->history_table[color][m.from_sq][m.to_sq];
    }

    return 0;
}

static void order_moves(const Board& board, std::vector<Move>& moves,
                        uint16_t tt_move = 0, const SearchState* state = nullptr, int ply = -1) {
    std::sort(moves.begin(), moves.end(), [&](const Move& a, const Move& b) {
        return move_score(board, a, tt_move, state, ply) >
               move_score(board, b, tt_move, state, ply);
    });
}

static int quiescence(Board& board, int alpha, int beta, int ply, int qdepth, SearchState& state) {
    state.nodes++;
    state.check_abort();
    if (state.aborted) return 0;

    int stand_pat = evaluate(board);

    if (stand_pat <= -MATE_SCORE + 1000) {
        return -MATE_SCORE + ply;
    }

    if (stand_pat >= beta) return beta;
    if (stand_pat > alpha) alpha = stand_pat;

    if (qdepth >= MAX_QSEARCH_DEPTH) return alpha;

    auto captures = board.generate_tactical_moves();
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

static int alpha_beta(Board& board, int depth, int alpha, int beta, int ply,
                      SearchState& state, bool last_was_null = false) {
    if (depth <= 0) {
        return quiescence(board, alpha, beta, ply, 0, state);
    }

    state.nodes++;
    state.check_abort();
    if (state.aborted) return 0;

    // TT probe
    uint64_t hash = board.hash();
    uint16_t tt_move = 0;
    TTEntry tt_entry;
    if (tt.probe(hash, tt_entry)) {
        tt_move = tt_entry.move;
        if (tt_entry.depth >= depth) {
            if (tt_entry.flag == TT_EXACT) return tt_entry.score;
            if (tt_entry.flag == TT_LOWER_BOUND && tt_entry.score >= beta) return tt_entry.score;
            if (tt_entry.flag == TT_UPPER_BOUND && tt_entry.score <= alpha) return tt_entry.score;
        }
    }

    // Syzygy probe
    if (TB_LARGEST > 0 && popcount(board.occupied()) <= TB_LARGEST && !state.aborted) {
        unsigned fathom_ep = board.en_passant_square() == -1 ? 0 : board.en_passant_square();
        unsigned wdl = tb_probe_wdl(
            board.white_pieces(), board.black_pieces(),
            board.bitboard_of(Piece::WhiteKing) | board.bitboard_of(Piece::BlackKing),
            board.bitboard_of(Piece::WhiteQueen) | board.bitboard_of(Piece::BlackQueen),
            board.bitboard_of(Piece::WhiteRook) | board.bitboard_of(Piece::BlackRook),
            board.bitboard_of(Piece::WhiteBishop) | board.bitboard_of(Piece::BlackBishop),
            board.bitboard_of(Piece::WhiteKnight) | board.bitboard_of(Piece::BlackKnight),
            board.bitboard_of(Piece::WhitePawn) | board.bitboard_of(Piece::BlackPawn),
            board.halfmove_clock(), board.castling_rights(), fathom_ep,
            board.side_to_move() == Color::White
        );

        if (wdl != TB_RESULT_FAILED) {
            int tb_score = 0;
            if (wdl == TB_WIN) tb_score = MATE_SCORE - MAX_PLY - ply;
            else if (wdl == TB_LOSS) tb_score = -MATE_SCORE + MAX_PLY + ply;
            else tb_score = 0; // DRAW or CURSED_WIN or BLESSED_LOSS

            // Exact bound 
            tt.store(hash, tb_score, depth, TT_EXACT, 0);
            return tb_score;
        }
    }

    Color enemy = (board.side_to_move() == Color::White) ? Color::Black : Color::White;
    int ksq = board.king_square();
    bool in_check = board.is_attacked(ksq, enemy);

    // Null Move Pruning
    if (!last_was_null && !in_check && depth >= 3 && board.has_non_pawn_material()) {
        int R = depth >= 6 ? 3 : 2;
        Board null_copy = board;
        null_copy.make_null_move();
        int null_score = -alpha_beta(null_copy, depth - 1 - R, -beta, -beta + 1, ply + 1, state, true);
        if (null_score >= beta) {
            return beta;
        }
    }

    auto moves = board.generate_legal_moves();

    if (moves.empty()) {
        if (in_check) return -MATE_SCORE + ply;
        return 0;  // stalemate
    }

    order_moves(board, moves, tt_move, &state, ply);

    int orig_alpha = alpha;
    Move best_move = moves[0];

    for (int i = 0; i < static_cast<int>(moves.size()); ++i) {
        if (state.aborted) return alpha;
        const Move& m = moves[i];
        bool is_capture = board.piece_at_sq(m.to_sq) != Piece::None;
        bool is_promo = m.promotion != Piece::None;
        bool is_quiet = !is_capture && !is_promo;

        Board copy = board;
        copy.make_move(m);
        int score;

        if (i == 0) {
            // First move: full window search
            score = -alpha_beta(copy, depth - 1, -beta, -alpha, ply + 1, state);
        } else {
            // LMR: reduce depth for late quiet moves
            int reduction = 0;
            if (is_quiet && i >= 3 && depth >= 3 && !in_check) {
                reduction = 1;
                if (i >= 6) reduction = 2;
                if (depth >= 6 && i >= 10) reduction = 3;
            }

            // Null window search (with possible reduction)
            score = -alpha_beta(copy, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, state);

            // Re-search at full depth if reduced search failed high
            if (reduction > 0 && score > alpha) {
                score = -alpha_beta(copy, depth - 1, -alpha - 1, -alpha, ply + 1, state);
            }

            // Re-search with full window if null window failed high
            if (score > alpha && score < beta) {
                score = -alpha_beta(copy, depth - 1, -beta, -alpha, ply + 1, state);
            }
        }

        if (score >= beta) {
            // Update killer moves and history for quiet moves
            if (is_quiet && ply < MAX_PLY) {
                state.killer_moves[ply][1] = state.killer_moves[ply][0];
                state.killer_moves[ply][0] = m;
                int color = static_cast<int>(board.side_to_move());
                state.history_table[color][m.from_sq][m.to_sq] += depth * depth;
            }
            tt.store(hash, score, depth, TT_LOWER_BOUND, m.encode());
            return beta;
        }
        if (score > alpha) {
            alpha = score;
            best_move = m;
        }
    }

    // Store TT entry
    TTFlag flag = (alpha <= orig_alpha) ? TT_UPPER_BOUND : TT_EXACT;
    tt.store(hash, alpha, depth, flag, best_move.encode());

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

SearchResult search_uci(const Board& board,
                        std::atomic<bool>& stop_flag,
                        int time_limit_ms,
                        int max_depth,
                        InfoCallback info_cb,
                        int thread_id) {
    auto start = Clock::now();

    SearchState state;
    state.stop_flag = &stop_flag;
    if (time_limit_ms > 0) {
        state.has_deadline = true;
        state.deadline = start + std::chrono::milliseconds(time_limit_ms);
    }

    SearchResult best;
    best.score = -INF;

    // Helper threads start at an offset depth for divergence
    int start_depth = 1;
    if (thread_id > 0) {
        start_depth = 1 + (thread_id % 3);
    }

    for (int depth = start_depth; depth <= max_depth; ++depth) {
        state.nodes = 0;
        state.aborted = false;

        SearchResult result = search_internal(board, depth, state);

        if (state.aborted) {
            if (best.score == -INF && result.best_move.to_uci() != "a1a1") {
                best = result;
            }
            break;
        }

        best = result;

        // Only thread 0 prints info and manages time control
        if (thread_id == 0) {
            if (info_cb) {
                auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                    Clock::now() - start).count();
                info_cb(best, static_cast<int>(elapsed));
            }

            if (best.score >= MATE_SCORE - 100 || best.score <= -MATE_SCORE + 100) {
                break;
            }

            // Don't start next depth if more than half the time is used
            if (time_limit_ms > 0) {
                auto elapsed = Clock::now() - start;
                if (elapsed * 2 >= std::chrono::milliseconds(time_limit_ms)) {
                    break;
                }
            }
        }
    }

    return best;
}

}  // namespace duchess
