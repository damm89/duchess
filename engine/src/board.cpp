// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "board.hpp"
#include "zobrist.h"
#include <sstream>

namespace duchess {

// --- Piece/char helpers ---

static char piece_to_char(Piece p) {
    switch (p) {
        case Piece::WhitePawn:   return 'P'; case Piece::WhiteKnight: return 'N';
        case Piece::WhiteBishop: return 'B'; case Piece::WhiteRook:   return 'R';
        case Piece::WhiteQueen:  return 'Q'; case Piece::WhiteKing:   return 'K';
        case Piece::BlackPawn:   return 'p'; case Piece::BlackKnight: return 'n';
        case Piece::BlackBishop: return 'b'; case Piece::BlackRook:   return 'r';
        case Piece::BlackQueen:  return 'q'; case Piece::BlackKing:   return 'k';
        default: return '.';
    }
}

static Piece char_to_piece(char c) {
    switch (c) {
        case 'P': return Piece::WhitePawn;   case 'N': return Piece::WhiteKnight;
        case 'B': return Piece::WhiteBishop; case 'R': return Piece::WhiteRook;
        case 'Q': return Piece::WhiteQueen;  case 'K': return Piece::WhiteKing;
        case 'p': return Piece::BlackPawn;   case 'n': return Piece::BlackKnight;
        case 'b': return Piece::BlackBishop; case 'r': return Piece::BlackRook;
        case 'q': return Piece::BlackQueen;  case 'k': return Piece::BlackKing;
        default: return Piece::None;
    }
}

// --- Move ---

std::string Move::to_uci() const {
    std::string uci;
    uci += static_cast<char>('a' + sq_col(from_sq));
    uci += static_cast<char>('1' + sq_row(from_sq));
    uci += static_cast<char>('a' + sq_col(to_sq));
    uci += static_cast<char>('1' + sq_row(to_sq));
    if (promotion != Piece::None) {
        char pc = piece_to_char(promotion);
        if (pc >= 'A' && pc <= 'Z') pc += 32;
        uci += pc;
    }
    return uci;
}

Move Move::from_uci(const std::string& uci) {
    Move m;
    m.from_sq = sq(uci[1] - '1', uci[0] - 'a');
    m.to_sq = sq(uci[3] - '1', uci[2] - 'a');
    if (uci.size() == 5) {
        switch (uci[4]) {
            case 'q': m.promotion = Piece::WhiteQueen; break;
            case 'r': m.promotion = Piece::WhiteRook; break;
            case 'b': m.promotion = Piece::WhiteBishop; break;
            case 'n': m.promotion = Piece::WhiteKnight; break;
            default: break;
        }
    }
    return m;
}

// --- Board basics ---

void Board::clear() {
    for (auto& b : pieces_) b = 0;
    side_to_move_ = Color::White;
    castling_ = 0;
    en_passant_sq_ = -1;
    halfmove_clock_ = 0;
    fullmove_number_ = 1;
}

void Board::set_starting_position() {
    parse_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
}

void Board::parse_fen(const std::string& fen) {
    clear();

    std::istringstream ss(fen);
    std::string placement, active, castling, ep;
    int half, full;
    ss >> placement >> active >> castling >> ep >> half >> full;

    int row = 7, col = 0;
    for (char c : placement) {
        if (c == '/') { row--; col = 0; }
        else if (c >= '1' && c <= '8') { col += (c - '0'); }
        else {
            Piece p = char_to_piece(c);
            if (p != Piece::None) set_bit(bb(p), sq(row, col));
            col++;
        }
    }

    side_to_move_ = (active == "b") ? Color::Black : Color::White;

    castling_ = 0;
    if (castling.find('K') != std::string::npos) castling_ |= CASTLE_WK;
    if (castling.find('Q') != std::string::npos) castling_ |= CASTLE_WQ;
    if (castling.find('k') != std::string::npos) castling_ |= CASTLE_BK;
    if (castling.find('q') != std::string::npos) castling_ |= CASTLE_BQ;

    if (ep != "-" && ep.size() == 2) {
        en_passant_sq_ = sq(ep[1] - '1', ep[0] - 'a');
    }

    halfmove_clock_ = half;
    fullmove_number_ = full;
    hash_ = compute_zobrist_hash(*this);
    nnue::refresh_accumulator(*this, accumulator_);
}

Board::Board() { set_starting_position(); }
Board::Board(const std::string& fen) { parse_fen(fen); }

Bitboard Board::white_pieces() const {
    return bb(Piece::WhitePawn) | bb(Piece::WhiteKnight) | bb(Piece::WhiteBishop) |
           bb(Piece::WhiteRook) | bb(Piece::WhiteQueen) | bb(Piece::WhiteKing);
}

Bitboard Board::black_pieces() const {
    return bb(Piece::BlackPawn) | bb(Piece::BlackKnight) | bb(Piece::BlackBishop) |
           bb(Piece::BlackRook) | bb(Piece::BlackQueen) | bb(Piece::BlackKing);
}

Bitboard Board::occupied() const { return white_pieces() | black_pieces(); }

Bitboard Board::own_pieces() const {
    return (side_to_move_ == Color::White) ? white_pieces() : black_pieces();
}

Bitboard Board::enemy_pieces() const {
    return (side_to_move_ == Color::White) ? black_pieces() : white_pieces();
}

Piece Board::piece_at_sq(int square) const {
    Bitboard mask = bit(square);
    for (int i = 0; i < 12; ++i) {
        if (pieces_[i] & mask)
            return static_cast<Piece>(i + 1);
    }
    return Piece::None;
}

Piece Board::piece_at(int row, int col) const {
    return piece_at_sq(sq(row, col));
}

void Board::set_piece_sq(int square, Piece piece) {
    // Remove any existing piece on that square
    remove_piece_sq(square);
    if (piece != Piece::None)
        set_bit(bb(piece), square);
}

void Board::set_piece(int row, int col, Piece piece) {
    set_piece_sq(sq(row, col), piece);
}

void Board::remove_piece_sq(int square) {
    Bitboard mask = bit(square);
    for (auto& b : pieces_) b &= ~mask;
}

int Board::king_square() const {
    Piece king = (side_to_move_ == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
    Bitboard k = bb(king);
    return __builtin_ctzll(k);
}

std::string Board::to_fen() const {
    std::string fen;
    for (int row = 7; row >= 0; --row) {
        int empty = 0;
        for (int col = 0; col < 8; ++col) {
            Piece p = piece_at(row, col);
            if (p == Piece::None) {
                empty++;
            } else {
                if (empty > 0) { fen += std::to_string(empty); empty = 0; }
                fen += piece_to_char(p);
            }
        }
        if (empty > 0) fen += std::to_string(empty);
        if (row > 0) fen += '/';
    }

    fen += (side_to_move_ == Color::White) ? " w" : " b";

    std::string c;
    if (castling_ & CASTLE_WK) c += 'K';
    if (castling_ & CASTLE_WQ) c += 'Q';
    if (castling_ & CASTLE_BK) c += 'k';
    if (castling_ & CASTLE_BQ) c += 'q';
    fen += ' ';
    fen += c.empty() ? "-" : c;

    fen += ' ';
    if (en_passant_sq_ >= 0) {
        fen += static_cast<char>('a' + sq_col(en_passant_sq_));
        fen += static_cast<char>('1' + sq_row(en_passant_sq_));
    } else {
        fen += '-';
    }

    fen += ' ' + std::to_string(halfmove_clock_);
    fen += ' ' + std::to_string(fullmove_number_);
    return fen;
}

// --- Attack detection ---

bool Board::is_attacked(int square, Color by) const {
    Bitboard occ = occupied();

    // Knight
    Piece enemy_knight = (by == Color::White) ? Piece::WhiteKnight : Piece::BlackKnight;
    if (KNIGHT_ATTACKS[square] & bb(enemy_knight)) return true;

    // King
    Piece enemy_king = (by == Color::White) ? Piece::WhiteKing : Piece::BlackKing;
    if (KING_ATTACKS[square] & bb(enemy_king)) return true;

    // Pawn
    int pawn_color = (by == Color::White) ? 1 : 0;  // reversed: pawn attacks FROM attacker TO square
    // If white attacks square, a white pawn must be on a square that attacks this square
    // PAWN_ATTACKS[0] = white pawn attack pattern. We check if any white pawn is on a square
    // whose attack pattern includes our target. Equivalently, we use the OPPOSITE color's
    // attack pattern from the target square to find attacking pawns.
    Piece enemy_pawn = (by == Color::White) ? Piece::WhitePawn : Piece::BlackPawn;
    if (PAWN_ATTACKS[pawn_color][square] & bb(enemy_pawn)) return true;

    // Sliding: bishop/queen on diagonals
    Piece enemy_bishop = (by == Color::White) ? Piece::WhiteBishop : Piece::BlackBishop;
    Piece enemy_queen = (by == Color::White) ? Piece::WhiteQueen : Piece::BlackQueen;
    Bitboard diag = bishop_attacks(square, occ);
    if (diag & (bb(enemy_bishop) | bb(enemy_queen))) return true;

    // Sliding: rook/queen on ranks/files
    Piece enemy_rook = (by == Color::White) ? Piece::WhiteRook : Piece::BlackRook;
    Bitboard straight = rook_attacks(square, occ);
    if (straight & (bb(enemy_rook) | bb(enemy_queen))) return true;

    return false;
}

// --- Move generation ---

void Board::generate_pawn_moves(std::vector<Move>& moves) const {
    bool white = (side_to_move_ == Color::White);
    Piece pawn = white ? Piece::WhitePawn : Piece::BlackPawn;
    Bitboard pawns = bb(pawn);
    Bitboard occ = occupied();
    Bitboard empty = ~occ;
    Bitboard enemies = enemy_pieces();
    int dir = white ? 8 : -8;
    int start_rank = white ? 1 : 6;
    int promo_rank = white ? 7 : 0;
    int ep_capture_rank = white ? 4 : 3;

    Piece promo_q = white ? Piece::WhiteQueen : Piece::BlackQueen;
    Piece promo_r = white ? Piece::WhiteRook : Piece::BlackRook;
    Piece promo_b = white ? Piece::WhiteBishop : Piece::BlackBishop;
    Piece promo_n = white ? Piece::WhiteKnight : Piece::BlackKnight;

    auto add_pawn_moves = [&](int from, int to) {
        if (sq_row(to) == promo_rank) {
            moves.push_back({from, to, promo_q});
            moves.push_back({from, to, promo_r});
            moves.push_back({from, to, promo_b});
            moves.push_back({from, to, promo_n});
        } else {
            moves.push_back({from, to});
        }
    };

    // Single push
    Bitboard single = white ? (pawns << 8) & empty : (pawns >> 8) & empty;
    Bitboard tmp = single;
    while (tmp) {
        int to = pop_lsb(tmp);
        add_pawn_moves(to - dir, to);
    }

    // Double push
    Bitboard rank_mask = white ? Bitboard(0xFF) << 16 : Bitboard(0xFF) << 40;
    Bitboard double_push = white
        ? ((single & (Bitboard(0xFF) << 16)) << 8) & empty
        : ((single & (Bitboard(0xFF) << 40)) >> 8) & empty;
    // Actually, simpler: double push is from start rank through one empty to another empty
    Bitboard start_pawns = pawns & (Bitboard(0xFF) << (start_rank * 8));
    Bitboard one_step = white ? (start_pawns << 8) & empty : (start_pawns >> 8) & empty;
    double_push = white ? (one_step << 8) & empty : (one_step >> 8) & empty;
    tmp = double_push;
    while (tmp) {
        int to = pop_lsb(tmp);
        moves.push_back({to - 2 * dir, to});
    }

    // Captures
    int color_idx = white ? 0 : 1;
    Bitboard copy_pawns = pawns;
    while (copy_pawns) {
        int from = pop_lsb(copy_pawns);
        Bitboard attacks = PAWN_ATTACKS[color_idx][from] & enemies;
        while (attacks) {
            int to = pop_lsb(attacks);
            add_pawn_moves(from, to);
        }

        // En passant
        if (en_passant_sq_ >= 0 && sq_row(from) == ep_capture_rank) {
            if (test_bit(PAWN_ATTACKS[color_idx][from], en_passant_sq_)) {
                moves.push_back({from, en_passant_sq_});
            }
        }
    }
}

void Board::generate_knight_moves(std::vector<Move>& moves) const {
    Piece knight = (side_to_move_ == Color::White) ? Piece::WhiteKnight : Piece::BlackKnight;
    Bitboard knights = bb(knight);
    Bitboard own = own_pieces();
    while (knights) {
        int from = pop_lsb(knights);
        Bitboard targets = KNIGHT_ATTACKS[from] & ~own;
        while (targets) {
            moves.push_back({from, pop_lsb(targets)});
        }
    }
}

void Board::generate_bishop_moves(std::vector<Move>& moves) const {
    Piece bishop = (side_to_move_ == Color::White) ? Piece::WhiteBishop : Piece::BlackBishop;
    Bitboard bishops = bb(bishop);
    Bitboard own = own_pieces();
    Bitboard occ = occupied();
    while (bishops) {
        int from = pop_lsb(bishops);
        Bitboard targets = bishop_attacks(from, occ) & ~own;
        while (targets) {
            moves.push_back({from, pop_lsb(targets)});
        }
    }
}

void Board::generate_rook_moves(std::vector<Move>& moves) const {
    Piece rook = (side_to_move_ == Color::White) ? Piece::WhiteRook : Piece::BlackRook;
    Bitboard rooks = bb(rook);
    Bitboard own = own_pieces();
    Bitboard occ = occupied();
    while (rooks) {
        int from = pop_lsb(rooks);
        Bitboard targets = rook_attacks(from, occ) & ~own;
        while (targets) {
            moves.push_back({from, pop_lsb(targets)});
        }
    }
}

void Board::generate_queen_moves(std::vector<Move>& moves) const {
    Piece queen = (side_to_move_ == Color::White) ? Piece::WhiteQueen : Piece::BlackQueen;
    Bitboard queens = bb(queen);
    Bitboard own = own_pieces();
    Bitboard occ = occupied();
    while (queens) {
        int from = pop_lsb(queens);
        Bitboard targets = queen_attacks(from, occ) & ~own;
        while (targets) {
            moves.push_back({from, pop_lsb(targets)});
        }
    }
}

void Board::generate_king_moves(std::vector<Move>& moves) const {
    int ksq = king_square();
    Bitboard own = own_pieces();
    Color enemy = (side_to_move_ == Color::White) ? Color::Black : Color::White;

    // Normal moves
    Bitboard targets = KING_ATTACKS[ksq] & ~own;
    while (targets) {
        moves.push_back({ksq, pop_lsb(targets)});
    }

    // Castling
    int base_row = (side_to_move_ == Color::White) ? 0 : 7;
    Bitboard occ = occupied();

    if (ksq == sq(base_row, 4) && !is_attacked(ksq, enemy)) {
        // Kingside
        uint8_t ks_flag = (side_to_move_ == Color::White) ? CASTLE_WK : CASTLE_BK;
        if ((castling_ & ks_flag) &&
            !test_bit(occ, sq(base_row, 5)) &&
            !test_bit(occ, sq(base_row, 6)) &&
            !is_attacked(sq(base_row, 5), enemy) &&
            !is_attacked(sq(base_row, 6), enemy)) {
            moves.push_back({ksq, sq(base_row, 6)});
        }

        // Queenside
        uint8_t qs_flag = (side_to_move_ == Color::White) ? CASTLE_WQ : CASTLE_BQ;
        if ((castling_ & qs_flag) &&
            !test_bit(occ, sq(base_row, 3)) &&
            !test_bit(occ, sq(base_row, 2)) &&
            !test_bit(occ, sq(base_row, 1)) &&
            !is_attacked(sq(base_row, 3), enemy) &&
            !is_attacked(sq(base_row, 2), enemy)) {
            moves.push_back({ksq, sq(base_row, 2)});
        }
    }
}

void Board::generate_pseudo_legal_moves(std::vector<Move>& moves) const {
    generate_pawn_moves(moves);
    generate_knight_moves(moves);
    generate_bishop_moves(moves);
    generate_rook_moves(moves);
    generate_queen_moves(moves);
    generate_king_moves(moves);
}

std::vector<Move> Board::generate_legal_moves() const {
    std::vector<Move> pseudo;
    generate_pseudo_legal_moves(pseudo);

    Color enemy = (side_to_move_ == Color::White) ? Color::Black : Color::White;
    Piece our_king = (side_to_move_ == Color::White) ? Piece::WhiteKing : Piece::BlackKing;

    std::vector<Move> legal;
    for (const auto& m : pseudo) {
        Board copy = *this;

        Piece moved = copy.piece_at_sq(m.from_sq);
        Piece captured = copy.piece_at_sq(m.to_sq);

        // En passant: remove the captured pawn
        bool is_ep = (moved == Piece::WhitePawn || moved == Piece::BlackPawn) &&
                     m.to_sq == en_passant_sq_ && en_passant_sq_ >= 0;
        if (is_ep) {
            int cap_sq = m.to_sq + ((side_to_move_ == Color::White) ? -8 : 8);
            copy.remove_piece_sq(cap_sq);
        }

        // Move the piece
        copy.remove_piece_sq(m.from_sq);
        if (m.to_sq >= 0) copy.remove_piece_sq(m.to_sq);
        Piece placed = (m.promotion != Piece::None) ? m.promotion : moved;
        set_bit(copy.bb(placed), m.to_sq);

        // Handle castling rook movement
        if (moved == our_king && std::abs(sq_col(m.to_sq) - sq_col(m.from_sq)) == 2) {
            int row = sq_row(m.from_sq);
            if (sq_col(m.to_sq) == 6) {
                // Kingside
                Piece rook = (side_to_move_ == Color::White) ? Piece::WhiteRook : Piece::BlackRook;
                clear_bit(copy.bb(rook), sq(row, 7));
                set_bit(copy.bb(rook), sq(row, 5));
            } else if (sq_col(m.to_sq) == 2) {
                // Queenside
                Piece rook = (side_to_move_ == Color::White) ? Piece::WhiteRook : Piece::BlackRook;
                clear_bit(copy.bb(rook), sq(row, 0));
                set_bit(copy.bb(rook), sq(row, 3));
            }
        }

        // Check if king is safe
        int ksq = __builtin_ctzll(copy.bb(our_king));
        if (!copy.is_attacked(ksq, enemy)) {
            legal.push_back(m);
        }
    }
    return legal;
}

void Board::generate_pseudo_tactical_moves(std::vector<Move>& moves) const {
    bool white = (side_to_move_ == Color::White);
    Bitboard enemies = enemy_pieces();
    Bitboard occ = occupied();

    // Pawn captures + queen promotions (pushes to promo rank)
    {
        Piece pawn = white ? Piece::WhitePawn : Piece::BlackPawn;
        Bitboard pawns = bb(pawn);
        int dir = white ? 8 : -8;
        int promo_rank = white ? 7 : 0;
        int ep_capture_rank = white ? 4 : 3;
        int color_idx = white ? 0 : 1;

        Piece promo_q = white ? Piece::WhiteQueen : Piece::BlackQueen;
        Piece promo_r = white ? Piece::WhiteRook : Piece::BlackRook;
        Piece promo_b = white ? Piece::WhiteBishop : Piece::BlackBishop;
        Piece promo_n = white ? Piece::WhiteKnight : Piece::BlackKnight;

        // Push promotions (single push to promo rank only)
        Bitboard promo_mask = Bitboard(0xFF) << (promo_rank * 8);
        Bitboard single = white ? (pawns << 8) & ~occ : (pawns >> 8) & ~occ;
        Bitboard push_promos = single & promo_mask;
        while (push_promos) {
            int to = pop_lsb(push_promos);
            moves.push_back({to - dir, to, promo_q});
            moves.push_back({to - dir, to, promo_r});
            moves.push_back({to - dir, to, promo_b});
            moves.push_back({to - dir, to, promo_n});
        }

        // Captures (including capture-promotions)
        Bitboard copy_pawns = pawns;
        while (copy_pawns) {
            int from = pop_lsb(copy_pawns);
            Bitboard attacks = PAWN_ATTACKS[color_idx][from] & enemies;
            while (attacks) {
                int to = pop_lsb(attacks);
                if (sq_row(to) == promo_rank) {
                    moves.push_back({from, to, promo_q});
                    moves.push_back({from, to, promo_r});
                    moves.push_back({from, to, promo_b});
                    moves.push_back({from, to, promo_n});
                } else {
                    moves.push_back({from, to});
                }
            }
            // En passant
            if (en_passant_sq_ >= 0 && sq_row(from) == ep_capture_rank) {
                if (test_bit(PAWN_ATTACKS[color_idx][from], en_passant_sq_)) {
                    moves.push_back({from, en_passant_sq_});
                }
            }
        }
    }

    // Knight captures
    {
        Piece knight = white ? Piece::WhiteKnight : Piece::BlackKnight;
        Bitboard knights = bb(knight);
        while (knights) {
            int from = pop_lsb(knights);
            Bitboard targets = KNIGHT_ATTACKS[from] & enemies;
            while (targets) {
                moves.push_back({from, pop_lsb(targets)});
            }
        }
    }

    // Bishop captures
    {
        Piece bishop = white ? Piece::WhiteBishop : Piece::BlackBishop;
        Bitboard bishops = bb(bishop);
        while (bishops) {
            int from = pop_lsb(bishops);
            Bitboard targets = bishop_attacks(from, occ) & enemies;
            while (targets) {
                moves.push_back({from, pop_lsb(targets)});
            }
        }
    }

    // Rook captures
    {
        Piece rook = white ? Piece::WhiteRook : Piece::BlackRook;
        Bitboard rooks = bb(rook);
        while (rooks) {
            int from = pop_lsb(rooks);
            Bitboard targets = rook_attacks(from, occ) & enemies;
            while (targets) {
                moves.push_back({from, pop_lsb(targets)});
            }
        }
    }

    // Queen captures
    {
        Piece queen = white ? Piece::WhiteQueen : Piece::BlackQueen;
        Bitboard queens = bb(queen);
        while (queens) {
            int from = pop_lsb(queens);
            Bitboard targets = queen_attacks(from, occ) & enemies;
            while (targets) {
                moves.push_back({from, pop_lsb(targets)});
            }
        }
    }

    // King captures (no castling)
    {
        int ksq = king_square();
        Bitboard targets = KING_ATTACKS[ksq] & enemies;
        while (targets) {
            moves.push_back({ksq, pop_lsb(targets)});
        }
    }
}

std::vector<Move> Board::generate_tactical_moves() const {
    std::vector<Move> pseudo;
    generate_pseudo_tactical_moves(pseudo);

    Color enemy = (side_to_move_ == Color::White) ? Color::Black : Color::White;
    Piece our_king = (side_to_move_ == Color::White) ? Piece::WhiteKing : Piece::BlackKing;

    std::vector<Move> legal;
    for (const auto& m : pseudo) {
        Board copy = *this;

        Piece moved = copy.piece_at_sq(m.from_sq);

        // En passant: remove the captured pawn
        bool is_ep = (moved == Piece::WhitePawn || moved == Piece::BlackPawn) &&
                     m.to_sq == en_passant_sq_ && en_passant_sq_ >= 0;
        if (is_ep) {
            int cap_sq = m.to_sq + ((side_to_move_ == Color::White) ? -8 : 8);
            copy.remove_piece_sq(cap_sq);
        }

        // Move the piece
        copy.remove_piece_sq(m.from_sq);
        if (m.to_sq >= 0) copy.remove_piece_sq(m.to_sq);
        Piece placed = (m.promotion != Piece::None) ? m.promotion : moved;
        set_bit(copy.bb(placed), m.to_sq);

        // Check if king is safe
        int ksq = __builtin_ctzll(copy.bb(our_king));
        if (!copy.is_attacked(ksq, enemy)) {
            legal.push_back(m);
        }
    }
    return legal;
}

// --- Make move ---

void Board::make_move(const Move& m) {
    Piece moved = piece_at_sq(m.from_sq);
    Piece captured = piece_at_sq(m.to_sq);

    // Save old castling/EP for hash updates
    uint8_t old_castling = castling_;
    int old_ep = en_passant_sq_;

    // XOR out old castling and EP from hash
    hash_ ^= castling_keys[castling_];
    if (en_passant_sq_ >= 0) hash_ ^= en_passant_keys[en_passant_sq_ % 8];

    // En passant capture
    bool is_ep = (moved == Piece::WhitePawn || moved == Piece::BlackPawn) &&
                 m.to_sq == en_passant_sq_ && en_passant_sq_ >= 0;

    int w_ksq = pop_lsb(bb(Piece::WhiteKing));
    int b_ksq = pop_lsb(bb(Piece::BlackKing));
    
    // We must put the bits back because pop_lsb clears them
    set_bit(bb(Piece::WhiteKing), w_ksq);
    set_bit(bb(Piece::BlackKing), b_ksq);

    bool king_moved = (moved == Piece::WhiteKing || moved == Piece::BlackKing);

    if (is_ep) {
        int cap_sq = m.to_sq + ((side_to_move_ == Color::White) ? -8 : 8);
        Piece ep_pawn = piece_at_sq(cap_sq);

        if (!king_moved) {
            int w_pt_ep = nnue::get_piece_type(ep_pawn, Color::White);
            int b_pt_ep = nnue::get_piece_type(ep_pawn, Color::Black);
            if (w_pt_ep != -1 && b_pt_ep != -1) {
                accumulator_.sub_feature(nnue::make_feature(w_ksq, w_pt_ep, cap_sq),
                                         nnue::make_feature(b_ksq, b_pt_ep, cap_sq));
            }
        }

        remove_piece_sq(cap_sq);
        hash_ ^= piece_keys[static_cast<int>(ep_pawn) - 1][cap_sq];
    }

    // NNUE: Sub moved piece and captured piece from old squares
    if (!king_moved) {
        int w_pt_moved = nnue::get_piece_type(moved, Color::White);
        int b_pt_moved = nnue::get_piece_type(moved, Color::Black);
        if (w_pt_moved != -1 && b_pt_moved != -1) {
            accumulator_.sub_feature(nnue::make_feature(w_ksq, w_pt_moved, m.from_sq),
                                     nnue::make_feature(b_ksq, b_pt_moved, m.from_sq));
        }
        if (captured != Piece::None) {
            int w_pt_cap = nnue::get_piece_type(captured, Color::White);
            int b_pt_cap = nnue::get_piece_type(captured, Color::Black);
            if (w_pt_cap != -1 && b_pt_cap != -1) {
                accumulator_.sub_feature(nnue::make_feature(w_ksq, w_pt_cap, m.to_sq),
                                         nnue::make_feature(b_ksq, b_pt_cap, m.to_sq));
            }
        }
    }

    // Hash: remove moved piece from source
    hash_ ^= piece_keys[static_cast<int>(moved) - 1][m.from_sq];

    // Hash: remove captured piece from destination (if any)
    if (captured != Piece::None) {
        hash_ ^= piece_keys[static_cast<int>(captured) - 1][m.to_sq];
    }

    // Remove piece from source, place at destination
    remove_piece_sq(m.from_sq);
    remove_piece_sq(m.to_sq);
    Piece placed = (m.promotion != Piece::None) ? m.promotion : moved;
    set_bit(bb(placed), m.to_sq);

    // NNUE: Add placed piece at new square
    if (!king_moved) {
        int w_pt_placed = nnue::get_piece_type(placed, Color::White);
        int b_pt_placed = nnue::get_piece_type(placed, Color::Black);
        if (w_pt_placed != -1 && b_pt_placed != -1) {
            accumulator_.add_feature(nnue::make_feature(w_ksq, w_pt_placed, m.to_sq),
                                     nnue::make_feature(b_ksq, b_pt_placed, m.to_sq));
        }
    }

    // Hash: add placed piece at destination
    hash_ ^= piece_keys[static_cast<int>(placed) - 1][m.to_sq];

    // Castling rook movement
    if ((moved == Piece::WhiteKing || moved == Piece::BlackKing) &&
        std::abs(sq_col(m.to_sq) - sq_col(m.from_sq)) == 2) {
        int row = sq_row(m.from_sq);
        Piece rook = (side_to_move_ == Color::White) ? Piece::WhiteRook : Piece::BlackRook;
        int rook_idx = static_cast<int>(rook) - 1;
        if (sq_col(m.to_sq) == 6) {
            int rook_from = sq(row, 7);
            int rook_to = sq(row, 5);
            clear_bit(bb(rook), rook_from);
            set_bit(bb(rook), rook_to);
            hash_ ^= piece_keys[rook_idx][rook_from];
            hash_ ^= piece_keys[rook_idx][rook_to];
        } else {
            int rook_from = sq(row, 0);
            int rook_to = sq(row, 3);
            clear_bit(bb(rook), rook_from);
            set_bit(bb(rook), rook_to);
            hash_ ^= piece_keys[rook_idx][rook_from];
            hash_ ^= piece_keys[rook_idx][rook_to];
        }
    }

    // Update castling rights
    if (moved == Piece::WhiteKing) castling_ &= ~(CASTLE_WK | CASTLE_WQ);
    if (moved == Piece::BlackKing) castling_ &= ~(CASTLE_BK | CASTLE_BQ);
    if (moved == Piece::WhiteRook && m.from_sq == sq(0, 7)) castling_ &= ~CASTLE_WK;
    if (moved == Piece::WhiteRook && m.from_sq == sq(0, 0)) castling_ &= ~CASTLE_WQ;
    if (moved == Piece::BlackRook && m.from_sq == sq(7, 7)) castling_ &= ~CASTLE_BK;
    if (moved == Piece::BlackRook && m.from_sq == sq(7, 0)) castling_ &= ~CASTLE_BQ;
    // Also clear if rook is captured
    if (m.to_sq == sq(0, 7)) castling_ &= ~CASTLE_WK;
    if (m.to_sq == sq(0, 0)) castling_ &= ~CASTLE_WQ;
    if (m.to_sq == sq(7, 7)) castling_ &= ~CASTLE_BK;
    if (m.to_sq == sq(7, 0)) castling_ &= ~CASTLE_BQ;

    // En passant square
    if ((moved == Piece::WhitePawn && m.to_sq - m.from_sq == 16) ||
        (moved == Piece::BlackPawn && m.from_sq - m.to_sq == 16)) {
        en_passant_sq_ = (m.from_sq + m.to_sq) / 2;
    } else {
        en_passant_sq_ = -1;
    }

    // XOR in new castling and EP
    hash_ ^= castling_keys[castling_];
    if (en_passant_sq_ >= 0) hash_ ^= en_passant_keys[en_passant_sq_ % 8];

    // Halfmove clock
    if (moved == Piece::WhitePawn || moved == Piece::BlackPawn || captured != Piece::None || is_ep)
        halfmove_clock_ = 0;
    else
        halfmove_clock_++;

    // Fullmove number
    if (side_to_move_ == Color::Black) fullmove_number_++;

    // Switch side
    side_to_move_ = (side_to_move_ == Color::White) ? Color::Black : Color::White;
    hash_ ^= side_key;

    if (king_moved) {
        nnue::refresh_accumulator(*this, accumulator_);
    }
}

void Board::make_null_move() {
    // XOR out old EP
    if (en_passant_sq_ >= 0) {
        hash_ ^= en_passant_keys[en_passant_sq_ % 8];
    }
    en_passant_sq_ = -1;

    // Flip side
    side_to_move_ = (side_to_move_ == Color::White) ? Color::Black : Color::White;
    hash_ ^= side_key;

    halfmove_clock_++;
    if (side_to_move_ == Color::White) fullmove_number_++;
}

bool Board::has_non_pawn_material() const {
    if (side_to_move_ == Color::White) {
        return (bb(Piece::WhiteKnight) | bb(Piece::WhiteBishop) |
                bb(Piece::WhiteRook) | bb(Piece::WhiteQueen)) != 0;
    } else {
        return (bb(Piece::BlackKnight) | bb(Piece::BlackBishop) |
                bb(Piece::BlackRook) | bb(Piece::BlackQueen)) != 0;
    }
}

}  // namespace duchess
