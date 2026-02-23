#include "eval.hpp"
#include "nnue.h"

namespace duchess {

// Piece-square tables (from white's perspective, index 0=a1 .. 63=h8)
// Values added to base piece value. Encourage central control and development.

static const int PAWN_PST[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0,
};

static const int KNIGHT_PST[64] = {
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
};

static const int BISHOP_PST[64] = {
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
};

static const int ROOK_PST[64] = {
     0,  0,  0,  5,  5,  0,  0,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
};

static const int QUEEN_PST[64] = {
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -10,  5,  5,  5,  5,  5,  0,-10,
      0,  0,  5,  5,  5,  5,  0, -5,
     -5,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
};

static const int KING_PST[64] = {
     20, 30, 10,  0,  0, 10, 30, 20,
     20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
};

// Mirror a square for black's perspective (flip rank)
static inline int mirror(int sq) {
    return sq ^ 56;  // flips rank: row 0 <-> row 7, etc.
}

static int eval_piece(Piece piece, Bitboard bb_pieces, const int* pst, int base_value, bool is_white_piece) {
    int score = 0;
    Bitboard copy = bb_pieces;
    while (copy) {
        int s = pop_lsb(copy);
        int pst_index = is_white_piece ? s : mirror(s);
        score += base_value + pst[pst_index];
    }
    return score;
}

int evaluate(const Board& board) {
    // Check for checkmate/stalemate first
    auto moves = board.generate_legal_moves();
    if (moves.empty()) {
        Color enemy = (board.side_to_move() == Color::White) ? Color::Black : Color::White;
        // Find our king
        Piece our_king = (board.side_to_move() == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
        Bitboard king_bb = board.side_to_move() == Color::White
            ? board.white_pieces() & ~(/* need king bb */(Bitboard)0)
            : board.black_pieces();
        // Check if in check by seeing if king is attacked
        // We need to find king square — use piece_at approach
        int ksq = -1;
        for (int s = 0; s < 64; ++s) {
            if (board.piece_at_sq(s) == our_king) { ksq = s; break; }
        }
        if (ksq >= 0 && board.is_attacked(ksq, enemy)) {
            return -MATE_SCORE;  // we are checkmated
        }
        return 0;  // stalemate
    }

    // Try NNUE eval first
    int nnue_score = nnue::evaluate(static_cast<int>(board.side_to_move()), *board.get_accumulator());
    if (nnue_score != 0) {
        return nnue_score;
    }

    int white_score = 0;
    int black_score = 0;

    // For each piece type, extract bitboard from board
    // We need access to piece bitboards — use the occupied approach
    for (int s = 0; s < 64; ++s) {
        Piece p = board.piece_at_sq(s);
        if (p == Piece::None) continue;

        bool white = is_white(p);
        int pst_idx = white ? s : mirror(s);

        switch (p) {
            case Piece::WhitePawn:   white_score += PAWN_VALUE   + PAWN_PST[pst_idx]; break;
            case Piece::WhiteKnight: white_score += KNIGHT_VALUE + KNIGHT_PST[pst_idx]; break;
            case Piece::WhiteBishop: white_score += BISHOP_VALUE + BISHOP_PST[pst_idx]; break;
            case Piece::WhiteRook:   white_score += ROOK_VALUE   + ROOK_PST[pst_idx]; break;
            case Piece::WhiteQueen:  white_score += QUEEN_VALUE  + QUEEN_PST[pst_idx]; break;
            case Piece::WhiteKing:   white_score += KING_PST[pst_idx]; break;
            case Piece::BlackPawn:   black_score += PAWN_VALUE   + PAWN_PST[pst_idx]; break;
            case Piece::BlackKnight: black_score += KNIGHT_VALUE + KNIGHT_PST[pst_idx]; break;
            case Piece::BlackBishop: black_score += BISHOP_VALUE + BISHOP_PST[pst_idx]; break;
            case Piece::BlackRook:   black_score += ROOK_VALUE   + ROOK_PST[pst_idx]; break;
            case Piece::BlackQueen:  black_score += QUEEN_VALUE  + QUEEN_PST[pst_idx]; break;
            case Piece::BlackKing:   black_score += KING_PST[pst_idx]; break;
            default: break;
        }
    }

    int score = white_score - black_score;
    return (board.side_to_move() == Color::White) ? score : -score;
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
