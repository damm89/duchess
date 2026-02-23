#pragma once

#include "bitboard.hpp"
#include <string>
#include <vector>

namespace duchess {

enum class Piece : uint8_t {
    None = 0,
    WhitePawn, WhiteKnight, WhiteBishop, WhiteRook, WhiteQueen, WhiteKing,
    BlackPawn, BlackKnight, BlackBishop, BlackRook, BlackQueen, BlackKing,
};

enum class Color : uint8_t {
    White = 0,
    Black = 1,
};

inline Color piece_color(Piece p) {
    return (static_cast<uint8_t>(p) <= static_cast<uint8_t>(Piece::WhiteKing))
           ? Color::White : Color::Black;
}

inline bool is_white(Piece p) { return p >= Piece::WhitePawn && p <= Piece::WhiteKing; }
inline bool is_black(Piece p) { return p >= Piece::BlackPawn && p <= Piece::BlackKing; }

struct Move {
    int from_sq = 0;
    int to_sq = 0;
    Piece promotion = Piece::None;

    std::string to_uci() const;
    static Move from_uci(const std::string& uci);

    // Compact encoding for TT storage: 6 bits from, 6 bits to, 4 bits promo
    uint16_t encode() const {
        return static_cast<uint16_t>(from_sq | (to_sq << 6) | (static_cast<int>(promotion) << 12));
    }
    static Move decode(uint16_t v) {
        Move m;
        m.from_sq = v & 0x3F;
        m.to_sq = (v >> 6) & 0x3F;
        m.promotion = static_cast<Piece>((v >> 12) & 0xF);
        return m;
    }
};

class Board {
public:
    Board();
    explicit Board(const std::string& fen);

    Piece piece_at(int row, int col) const;
    Piece piece_at_sq(int square) const;
    void set_piece(int row, int col, Piece piece);
    void set_piece_sq(int square, Piece piece);
    void remove_piece_sq(int square);

    Color side_to_move() const { return side_to_move_; }
    uint8_t castling_rights() const { return castling_; }
    int en_passant_square() const { return en_passant_sq_; }
    int halfmove_clock() const { return halfmove_clock_; }
    uint64_t hash() const { return hash_; }
    std::string to_fen() const;

    std::vector<Move> generate_legal_moves() const;
    std::vector<Move> generate_tactical_moves() const;
    void make_move(const Move& m);
    void make_null_move();

    // Check if a square is attacked by the given color
    bool is_attacked(int square, Color by) const;

    // Returns true if side to move has non-pawn, non-king pieces
    bool has_non_pawn_material() const;

    int king_square() const;

    // Aggregate bitboards
    Bitboard white_pieces() const;
    Bitboard black_pieces() const;
    Bitboard occupied() const;

    Bitboard bitboard_of(Piece p) const { return pieces_[static_cast<int>(p) - 1]; }

private:
    // 12 piece bitboards
    Bitboard pieces_[12] = {};  // indexed by (Piece - 1)
    Color side_to_move_ = Color::White;
    uint8_t castling_ = 0;  // bits: 0=WK, 1=WQ, 2=BK, 3=BQ
    int en_passant_sq_ = -1;  // target square or -1
    int halfmove_clock_ = 0;
    int fullmove_number_ = 1;
    uint64_t hash_ = 0;

    static constexpr uint8_t CASTLE_WK = 1;
    static constexpr uint8_t CASTLE_WQ = 2;
    static constexpr uint8_t CASTLE_BK = 4;
    static constexpr uint8_t CASTLE_BQ = 8;

    Bitboard& bb(Piece p) { return pieces_[static_cast<int>(p) - 1]; }
    Bitboard bb(Piece p) const { return pieces_[static_cast<int>(p) - 1]; }

    void clear();
    void set_starting_position();
    void parse_fen(const std::string& fen);

    Bitboard own_pieces() const;
    Bitboard enemy_pieces() const;

    void generate_pawn_moves(std::vector<Move>& moves) const;
    void generate_knight_moves(std::vector<Move>& moves) const;
    void generate_bishop_moves(std::vector<Move>& moves) const;
    void generate_rook_moves(std::vector<Move>& moves) const;
    void generate_queen_moves(std::vector<Move>& moves) const;
    void generate_king_moves(std::vector<Move>& moves) const;
    void generate_pseudo_legal_moves(std::vector<Move>& moves) const;
    void generate_pseudo_tactical_moves(std::vector<Move>& moves) const;
};

}  // namespace duchess
