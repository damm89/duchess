#include "bitboard.hpp"

namespace duchess {

Bitboard KNIGHT_ATTACKS[64];
Bitboard KING_ATTACKS[64];
Bitboard PAWN_ATTACKS[2][64];

static Bitboard compute_knight_attacks(int s) {
    Bitboard bb = 0;
    int r = sq_row(s), c = sq_col(s);
    static const int offsets[8][2] = {
        {-2,-1},{-2,1},{-1,-2},{-1,2},{1,-2},{1,2},{2,-1},{2,1}
    };
    for (auto& off : offsets) {
        int nr = r + off[0], nc = c + off[1];
        if (nr >= 0 && nr < 8 && nc >= 0 && nc < 8)
            set_bit(bb, sq(nr, nc));
    }
    return bb;
}

static Bitboard compute_king_attacks(int s) {
    Bitboard bb = 0;
    int r = sq_row(s), c = sq_col(s);
    for (int dr = -1; dr <= 1; ++dr)
        for (int dc = -1; dc <= 1; ++dc) {
            if (dr == 0 && dc == 0) continue;
            int nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr < 8 && nc >= 0 && nc < 8)
                set_bit(bb, sq(nr, nc));
        }
    return bb;
}

static Bitboard compute_pawn_attacks(int color, int s) {
    Bitboard bb = 0;
    int r = sq_row(s), c = sq_col(s);
    int dir = (color == 0) ? 1 : -1;  // white=up, black=down
    int nr = r + dir;
    if (nr >= 0 && nr < 8) {
        if (c > 0) set_bit(bb, sq(nr, c - 1));
        if (c < 7) set_bit(bb, sq(nr, c + 1));
    }
    return bb;
}

void init_attack_tables() {
    for (int s = 0; s < 64; ++s) {
        KNIGHT_ATTACKS[s] = compute_knight_attacks(s);
        KING_ATTACKS[s] = compute_king_attacks(s);
        PAWN_ATTACKS[0][s] = compute_pawn_attacks(0, s);
        PAWN_ATTACKS[1][s] = compute_pawn_attacks(1, s);
    }
}

// Classical ray-based sliding attacks

Bitboard rook_attacks(int square, Bitboard occupied) {
    Bitboard attacks = 0;
    int r = sq_row(square), c = sq_col(square);
    static const int dirs[4][2] = {{1,0},{-1,0},{0,1},{0,-1}};
    for (auto& dir : dirs) {
        for (int dist = 1; dist < 8; ++dist) {
            int nr = r + dir[0] * dist, nc = c + dir[1] * dist;
            if (nr < 0 || nr > 7 || nc < 0 || nc > 7) break;
            int target = sq(nr, nc);
            set_bit(attacks, target);
            if (test_bit(occupied, target)) break;
        }
    }
    return attacks;
}

Bitboard bishop_attacks(int square, Bitboard occupied) {
    Bitboard attacks = 0;
    int r = sq_row(square), c = sq_col(square);
    static const int dirs[4][2] = {{1,1},{1,-1},{-1,1},{-1,-1}};
    for (auto& dir : dirs) {
        for (int dist = 1; dist < 8; ++dist) {
            int nr = r + dir[0] * dist, nc = c + dir[1] * dist;
            if (nr < 0 || nr > 7 || nc < 0 || nc > 7) break;
            int target = sq(nr, nc);
            set_bit(attacks, target);
            if (test_bit(occupied, target)) break;
        }
    }
    return attacks;
}

}  // namespace duchess
