// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "eval.hpp"
#include "nnue.h"
#include "bitboard.hpp"

namespace duchess {

// ============================================================
//  Piece-square tables (middlegame)
// ============================================================

static const int PAWN_MG_PST[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0,
};

static const int PAWN_EG_PST[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
    10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10,
    15, 15, 15, 20, 20, 15, 15, 15,
    25, 25, 25, 30, 30, 25, 25, 25,
    35, 35, 35, 40, 40, 35, 35, 35,
    60, 60, 60, 60, 60, 60, 60, 60,
     0,  0,  0,  0,  0,  0,  0,  0,
};

static const int KNIGHT_MG_PST[64] = {
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
};

static const int KNIGHT_EG_PST[64] = {
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
};

static const int BISHOP_MG_PST[64] = {
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
};

static const int BISHOP_EG_PST[64] = {
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5, 10, 15, 15, 10,  5,-10,
    -10,  5, 10, 15, 15, 10,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
};

static const int ROOK_MG_PST[64] = {
     0,  0,  0,  5,  5,  0,  0,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
};

static const int ROOK_EG_PST[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,
     5,  5,  5,  5,  5,  5,  5,  5,
     5,  5,  5,  5,  5,  5,  5,  5,
     5,  5,  5,  5,  5,  5,  5,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,
};

static const int QUEEN_MG_PST[64] = {
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -10,  5,  5,  5,  5,  5,  0,-10,
      0,  0,  5,  5,  5,  5,  0, -5,
     -5,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
};

static const int QUEEN_EG_PST[64] = {
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5, 10, 10,  5,  0, -5,
     -5,  0,  5, 10, 10,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
};

static const int KING_MG_PST[64] = {
     20, 30, 10,  0,  0, 10, 30, 20,
     20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
};

static const int KING_EG_PST[64] = {
    -50,-30,-30,-30,-30,-30,-30,-50,
    -30,-10,  0,  0,  0,  0,-10,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,-10,  0,  0,  0,  0,-10,-30,
    -50,-30,-30,-30,-30,-30,-30,-50,
};

// Mirror a square for black's perspective (flip rank)
static inline int mirror(int sq) {
    return sq ^ 56;
}

// ============================================================
//  Eval constants
// ============================================================

static constexpr int BISHOP_PAIR_BONUS   = 50;
static constexpr int DOUBLED_PAWN_PENALTY = -15;
static constexpr int ISOLATED_PAWN_PENALTY = -20;
static constexpr int PASSED_PAWN_BONUS[8] = { 0, 10, 20, 35, 60, 100, 150, 0 }; // by rank (0=rank1, 7=rank8)
static constexpr int ROOK_OPEN_FILE_BONUS = 25;
static constexpr int ROOK_SEMI_OPEN_FILE_BONUS = 15;
static constexpr int MOBILITY_KNIGHT = 4;
static constexpr int MOBILITY_BISHOP = 5;
static constexpr int MOBILITY_ROOK   = 2;
static constexpr int MOBILITY_QUEEN  = 1;

// King safety: pawn shield bonus per pawn in front of king
static constexpr int PAWN_SHIELD_BONUS = 15;

// File masks (column bitmasks)
static constexpr Bitboard FILE_MASK[8] = {
    0x0101010101010101ULL << 0,
    0x0101010101010101ULL << 1,
    0x0101010101010101ULL << 2,
    0x0101010101010101ULL << 3,
    0x0101010101010101ULL << 4,
    0x0101010101010101ULL << 5,
    0x0101010101010101ULL << 6,
    0x0101010101010101ULL << 7,
};

// Adjacent file masks
static Bitboard adjacent_files(int file) {
    Bitboard mask = 0;
    if (file > 0) mask |= FILE_MASK[file - 1];
    if (file < 7) mask |= FILE_MASK[file + 1];
    return mask;
}

// ============================================================
//  Game phase calculation
// ============================================================

// Phase weights: total phase = 24 (4 knights + 4 bishops + 4 rooks + 2 queens = 4*1 + 4*1 + 4*2 + 2*4 = 24)
static constexpr int PHASE_KNIGHT = 1;
static constexpr int PHASE_BISHOP = 1;
static constexpr int PHASE_ROOK   = 2;
static constexpr int PHASE_QUEEN  = 4;
static constexpr int TOTAL_PHASE  = 24;

static int compute_phase(const Board& board) {
    int phase = TOTAL_PHASE;
    phase -= popcount(board.bitboard_of(Piece::WhiteKnight) | board.bitboard_of(Piece::BlackKnight)) * PHASE_KNIGHT;
    phase -= popcount(board.bitboard_of(Piece::WhiteBishop) | board.bitboard_of(Piece::BlackBishop)) * PHASE_BISHOP;
    phase -= popcount(board.bitboard_of(Piece::WhiteRook) | board.bitboard_of(Piece::BlackRook)) * PHASE_ROOK;
    phase -= popcount(board.bitboard_of(Piece::WhiteQueen) | board.bitboard_of(Piece::BlackQueen)) * PHASE_QUEEN;
    if (phase < 0) phase = 0;
    return phase; // 0 = full middlegame, 24 = pure endgame
}

// Taper between middlegame and endgame scores
static int taper(int mg, int eg, int phase) {
    return (mg * (TOTAL_PHASE - phase) + eg * phase) / TOTAL_PHASE;
}

// ============================================================
//  Pawn structure evaluation
// ============================================================

struct PawnInfo {
    int mg = 0;
    int eg = 0;
};

static PawnInfo eval_pawns(Bitboard white_pawns, Bitboard black_pawns) {
    PawnInfo info;

    // White pawns
    Bitboard wp = white_pawns;
    while (wp) {
        int s = pop_lsb(wp);
        int file = sq_col(s);
        int rank = sq_row(s);

        // Doubled pawns: another white pawn on the same file
        if (popcount(white_pawns & FILE_MASK[file]) > 1) {
            info.mg += DOUBLED_PAWN_PENALTY;
            info.eg += DOUBLED_PAWN_PENALTY;
        }

        // Isolated pawns: no friendly pawns on adjacent files
        if (!(white_pawns & adjacent_files(file))) {
            info.mg += ISOLATED_PAWN_PENALTY;
            info.eg += ISOLATED_PAWN_PENALTY - 5; // slightly worse in endgame
        }

        // Passed pawns: no enemy pawns on same or adjacent files ahead
        Bitboard ahead_mask = 0;
        for (int r = rank + 1; r < 8; ++r) {
            ahead_mask |= bit(sq(r, file));
            if (file > 0) ahead_mask |= bit(sq(r, file - 1));
            if (file < 7) ahead_mask |= bit(sq(r, file + 1));
        }
        if (!(black_pawns & ahead_mask)) {
            info.mg += PASSED_PAWN_BONUS[rank] / 2;      // less important in middlegame
            info.eg += PASSED_PAWN_BONUS[rank];            // very important in endgame
        }
    }

    // Black pawns (mirrored)
    Bitboard bp = black_pawns;
    while (bp) {
        int s = pop_lsb(bp);
        int file = sq_col(s);
        int rank = sq_row(s);

        if (popcount(black_pawns & FILE_MASK[file]) > 1) {
            info.mg -= DOUBLED_PAWN_PENALTY;
            info.eg -= DOUBLED_PAWN_PENALTY;
        }

        if (!(black_pawns & adjacent_files(file))) {
            info.mg -= ISOLATED_PAWN_PENALTY;
            info.eg -= ISOLATED_PAWN_PENALTY - 5;
        }

        // Passed pawn for black: no white pawns on same or adjacent files below
        Bitboard ahead_mask = 0;
        for (int r = rank - 1; r >= 0; --r) {
            ahead_mask |= bit(sq(r, file));
            if (file > 0) ahead_mask |= bit(sq(r, file - 1));
            if (file < 7) ahead_mask |= bit(sq(r, file + 1));
        }
        if (!(white_pawns & ahead_mask)) {
            int mirrored_rank = 7 - rank;
            info.mg -= PASSED_PAWN_BONUS[mirrored_rank] / 2;
            info.eg -= PASSED_PAWN_BONUS[mirrored_rank];
        }
    }

    return info;
}

// ============================================================
//  Piece evaluation helpers
// ============================================================

static int eval_rooks_on_files(Bitboard rooks, Bitboard own_pawns, Bitboard enemy_pawns) {
    int score = 0;
    while (rooks) {
        int s = pop_lsb(rooks);
        int file = sq_col(s);
        bool own_pawn_on_file = (own_pawns & FILE_MASK[file]) != 0;
        bool enemy_pawn_on_file = (enemy_pawns & FILE_MASK[file]) != 0;

        if (!own_pawn_on_file && !enemy_pawn_on_file) {
            score += ROOK_OPEN_FILE_BONUS;
        } else if (!own_pawn_on_file) {
            score += ROOK_SEMI_OPEN_FILE_BONUS;
        }
    }
    return score;
}

static int eval_mobility(const Board& board, Color color) {
    int score = 0;
    Bitboard occ = board.occupied();
    Bitboard own = (color == Color::White) ? board.white_pieces() : board.black_pieces();

    // Knights
    Bitboard knights = (color == Color::White) ? board.bitboard_of(Piece::WhiteKnight) : board.bitboard_of(Piece::BlackKnight);
    while (knights) {
        int s = pop_lsb(knights);
        int moves = popcount(KNIGHT_ATTACKS[s] & ~own);
        score += (moves - 4) * MOBILITY_KNIGHT; // centered around 4 moves
    }

    // Bishops
    Bitboard bishops = (color == Color::White) ? board.bitboard_of(Piece::WhiteBishop) : board.bitboard_of(Piece::BlackBishop);
    while (bishops) {
        int s = pop_lsb(bishops);
        int moves = popcount(bishop_attacks(s, occ) & ~own);
        score += (moves - 6) * MOBILITY_BISHOP;
    }

    // Rooks
    Bitboard rooks = (color == Color::White) ? board.bitboard_of(Piece::WhiteRook) : board.bitboard_of(Piece::BlackRook);
    while (rooks) {
        int s = pop_lsb(rooks);
        int moves = popcount(rook_attacks(s, occ) & ~own);
        score += (moves - 7) * MOBILITY_ROOK;
    }

    // Queens (small weight to avoid queen wandering)
    Bitboard queens = (color == Color::White) ? board.bitboard_of(Piece::WhiteQueen) : board.bitboard_of(Piece::BlackQueen);
    while (queens) {
        int s = pop_lsb(queens);
        int moves = popcount(queen_attacks(s, occ) & ~own);
        score += (moves - 14) * MOBILITY_QUEEN;
    }

    return score;
}

static int eval_king_safety(const Board& board, Color color) {
    int score = 0;
    Bitboard own_pawns = (color == Color::White) ? board.bitboard_of(Piece::WhitePawn) : board.bitboard_of(Piece::BlackPawn);
    Bitboard king_bb = (color == Color::White) ? board.bitboard_of(Piece::WhiteKing) : board.bitboard_of(Piece::BlackKing);

    if (!king_bb) return 0;
    int ksq = ctzll(king_bb);
    int kfile = sq_col(ksq);
    int krank = sq_row(ksq);

    // Pawn shield: count friendly pawns on the 1-2 ranks ahead of king, on king file and adjacent
    int shield_count = 0;
    int forward = (color == Color::White) ? 1 : -1;

    for (int df = -1; df <= 1; ++df) {
        int f = kfile + df;
        if (f < 0 || f > 7) continue;
        for (int dr = 1; dr <= 2; ++dr) {
            int r = krank + forward * dr;
            if (r < 0 || r > 7) continue;
            if (test_bit(own_pawns, sq(r, f))) {
                shield_count++;
            }
        }
    }

    score += shield_count * PAWN_SHIELD_BONUS;
    return score;
}

// ============================================================
//  Main evaluation function
// ============================================================

int evaluate(const Board& board) {
    // Check for checkmate/stalemate first
    auto moves = board.generate_legal_moves();
    if (moves.empty()) {
        Color enemy = (board.side_to_move() == Color::White) ? Color::Black : Color::White;
        Piece our_king = (board.side_to_move() == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
        int ksq = -1;
        for (int s = 0; s < 64; ++s) {
            if (board.piece_at_sq(s) == our_king) { ksq = s; break; }
        }
        if (ksq >= 0 && board.is_attacked(ksq, enemy)) {
            return -MATE_SCORE;
        }
        return 0;  // stalemate
    }

    // ---- Classical evaluation (always computed) ----

    int mg_score = 0;
    int eg_score = 0;

    // Material + piece-square tables
    for (int s = 0; s < 64; ++s) {
        Piece p = board.piece_at_sq(s);
        if (p == Piece::None) continue;

        bool white = is_white(p);
        int pst_idx = white ? s : mirror(s);
        int sign = white ? 1 : -1;

        switch (p) {
            case Piece::WhitePawn: case Piece::BlackPawn:
                mg_score += sign * (PAWN_VALUE + PAWN_MG_PST[pst_idx]);
                eg_score += sign * (PAWN_VALUE + PAWN_EG_PST[pst_idx]);
                break;
            case Piece::WhiteKnight: case Piece::BlackKnight:
                mg_score += sign * (KNIGHT_VALUE + KNIGHT_MG_PST[pst_idx]);
                eg_score += sign * (KNIGHT_VALUE + KNIGHT_EG_PST[pst_idx]);
                break;
            case Piece::WhiteBishop: case Piece::BlackBishop:
                mg_score += sign * (BISHOP_VALUE + BISHOP_MG_PST[pst_idx]);
                eg_score += sign * (BISHOP_VALUE + BISHOP_EG_PST[pst_idx]);
                break;
            case Piece::WhiteRook: case Piece::BlackRook:
                mg_score += sign * (ROOK_VALUE + ROOK_MG_PST[pst_idx]);
                eg_score += sign * (ROOK_VALUE + ROOK_EG_PST[pst_idx]);
                break;
            case Piece::WhiteQueen: case Piece::BlackQueen:
                mg_score += sign * (QUEEN_VALUE + QUEEN_MG_PST[pst_idx]);
                eg_score += sign * (QUEEN_VALUE + QUEEN_EG_PST[pst_idx]);
                break;
            case Piece::WhiteKing: case Piece::BlackKing:
                mg_score += sign * KING_MG_PST[pst_idx];
                eg_score += sign * KING_EG_PST[pst_idx];
                break;
            default: break;
        }
    }

    // Pawn structure (passed, doubled, isolated)
    Bitboard white_pawns = board.bitboard_of(Piece::WhitePawn);
    Bitboard black_pawns = board.bitboard_of(Piece::BlackPawn);
    PawnInfo pawn_info = eval_pawns(white_pawns, black_pawns);
    mg_score += pawn_info.mg;
    eg_score += pawn_info.eg;

    // Bishop pair
    if (popcount(board.bitboard_of(Piece::WhiteBishop)) >= 2)
        mg_score += BISHOP_PAIR_BONUS;
    if (popcount(board.bitboard_of(Piece::BlackBishop)) >= 2)
        mg_score -= BISHOP_PAIR_BONUS;

    // Rooks on open/semi-open files
    mg_score += eval_rooks_on_files(board.bitboard_of(Piece::WhiteRook), white_pawns, black_pawns);
    mg_score -= eval_rooks_on_files(board.bitboard_of(Piece::BlackRook), black_pawns, white_pawns);

    // Mobility
    int white_mob = eval_mobility(board, Color::White);
    int black_mob = eval_mobility(board, Color::Black);
    mg_score += white_mob;
    eg_score += white_mob;
    mg_score -= black_mob;
    eg_score -= black_mob;

    // King safety (middlegame only)
    mg_score += eval_king_safety(board, Color::White);
    mg_score -= eval_king_safety(board, Color::Black);

    // Phase tapering
    int phase = compute_phase(board);
    int classical_score = taper(mg_score, eg_score, phase);
    classical_score = (board.side_to_move() == Color::White) ? classical_score : -classical_score;

    // Blend with NNUE if available
    // Weights: NNUE 50%, Classical 50% — shift toward NNUE as network matures
    int nnue_score = nnue::evaluate(static_cast<int>(board.side_to_move()), *board.get_accumulator());
    if (nnue_score != 0) {
        return (nnue_score + classical_score) / 2;
    }

    return classical_score;
}

bool is_checkmate(const Board& board) {
    auto moves = board.generate_legal_moves();
    if (!moves.empty()) return false;

    Color enemy = (board.side_to_move() == Color::White) ? Color::Black : Color::White;
    Piece our_king = (board.side_to_move() == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
    for (int s = 0; s < 64; ++s) {
        if (board.piece_at_sq(s) == our_king) {
            return board.is_attacked(s, enemy);
        }
    }
    return false;
}

bool is_stalemate(const Board& board) {
    auto moves = board.generate_legal_moves();
    if (!moves.empty()) return false;

    Color enemy = (board.side_to_move() == Color::White) ? Color::Black : Color::White;
    Piece our_king = (board.side_to_move() == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
    for (int s = 0; s < 64; ++s) {
        if (board.piece_at_sq(s) == our_king) {
            return !board.is_attacked(s, enemy);
        }
    }
    return false;
}

}  // namespace duchess
