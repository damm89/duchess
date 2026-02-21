#include <catch2/catch_test_macros.hpp>
#include <algorithm>
#include <vector>
#include <string>
#include "board.hpp"

using namespace duchess;

struct InitTables2 {
    InitTables2() { init_attack_tables(); }
};
static InitTables2 _init2;

// Helper: check if a move from (fr,fc) to (tr,tc) is in the list
static bool has_move(const std::vector<Move>& moves, int fr, int fc, int tr, int tc) {
    int from = sq(fr, fc), to = sq(tr, tc);
    return std::any_of(moves.begin(), moves.end(), [&](const Move& m) {
        return m.from_sq == from && m.to_sq == to && m.promotion == Piece::None;
    });
}

static bool has_promo(const std::vector<Move>& moves, int fr, int fc, int tr, int tc, Piece promo) {
    int from = sq(fr, fc), to = sq(tr, tc);
    return std::any_of(moves.begin(), moves.end(), [&](const Move& m) {
        return m.from_sq == from && m.to_sq == to && m.promotion == promo;
    });
}

static int count_from(const std::vector<Move>& moves, int fr, int fc) {
    int from = sq(fr, fc);
    return static_cast<int>(std::count_if(moves.begin(), moves.end(), [&](const Move& m) {
        return m.from_sq == from;
    }));
}

// ===== PAWN TESTS =====

TEST_CASE("White pawn single push", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/8/4P3/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 1, 4, 2, 4));
}

TEST_CASE("White pawn double push from rank 2", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/8/4P3/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 1, 4, 3, 4));
}

TEST_CASE("White pawn cannot double push from rank 3", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/4P3/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 2, 4, 3, 4));
    REQUIRE_FALSE(has_move(moves, 2, 4, 4, 4));
}

TEST_CASE("White pawn blocked cannot advance", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/4p3/4P3/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 1, 4, 2, 4));
    REQUIRE_FALSE(has_move(moves, 1, 4, 3, 4));
}

TEST_CASE("White pawn captures diagonally", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/3p1p2/4P3/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 1, 4, 2, 3));
    REQUIRE(has_move(moves, 1, 4, 2, 5));
}

TEST_CASE("White pawn does not capture own pieces", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/3P1P2/4P3/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 1, 4, 2, 3));
    REQUIRE_FALSE(has_move(moves, 1, 4, 2, 5));
}

TEST_CASE("White pawn en passant", "[movegen][pawn]") {
    Board board("7k/8/8/3pP3/8/8/8/K7 w - d6 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 4, 4, 5, 3));
}

TEST_CASE("White pawn promotion", "[movegen][pawn]") {
    Board board("7k/4P3/8/8/8/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_promo(moves, 6, 4, 7, 4, Piece::WhiteQueen));
    REQUIRE(has_promo(moves, 6, 4, 7, 4, Piece::WhiteRook));
    REQUIRE(has_promo(moves, 6, 4, 7, 4, Piece::WhiteBishop));
    REQUIRE(has_promo(moves, 6, 4, 7, 4, Piece::WhiteKnight));
    REQUIRE_FALSE(has_move(moves, 6, 4, 7, 4));
}

TEST_CASE("Black pawn moves south", "[movegen][pawn]") {
    Board board("7k/4p3/8/8/8/8/8/K7 b - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 6, 4, 5, 4));
    REQUIRE(has_move(moves, 6, 4, 4, 4));
}

TEST_CASE("Black pawn promotion", "[movegen][pawn]") {
    Board board("7k/8/8/8/8/8/4p3/K7 b - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_promo(moves, 1, 4, 0, 4, Piece::BlackQueen));
    REQUIRE(has_promo(moves, 1, 4, 0, 4, Piece::BlackRook));
    REQUIRE(has_promo(moves, 1, 4, 0, 4, Piece::BlackBishop));
    REQUIRE(has_promo(moves, 1, 4, 0, 4, Piece::BlackKnight));
}

// ===== KNIGHT TESTS =====

TEST_CASE("Knight moves from center", "[movegen][knight]") {
    Board board("7k/8/8/8/3N4/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 3, 3) == 8);
}

TEST_CASE("Knight moves from corner", "[movegen][knight]") {
    Board board("7k/8/8/8/8/8/8/NK6 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 0, 0) == 2);
}

TEST_CASE("Knight cannot capture own piece", "[movegen][knight]") {
    Board board("7k/8/4P3/8/3N4/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 3, 3, 5, 4));
}

TEST_CASE("Knight captures enemy piece", "[movegen][knight]") {
    Board board("7k/8/4p3/8/3N4/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 3, 3, 5, 4));
}

// ===== BISHOP TESTS =====

TEST_CASE("Bishop moves on empty board", "[movegen][bishop]") {
    Board board("7k/8/8/8/3B4/8/8/1K6 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 3, 3) == 13);
}

TEST_CASE("Bishop blocked by own piece", "[movegen][bishop]") {
    Board board("7k/8/5P2/8/3B4/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 3, 3, 4, 4));
    REQUIRE_FALSE(has_move(moves, 3, 3, 5, 5));
    REQUIRE_FALSE(has_move(moves, 3, 3, 6, 6));
}

TEST_CASE("Bishop captures then stops", "[movegen][bishop]") {
    Board board("7k/8/5p2/8/3B4/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 3, 3, 5, 5));
    REQUIRE_FALSE(has_move(moves, 3, 3, 6, 6));
}

// ===== ROOK TESTS =====

TEST_CASE("Rook moves on empty board", "[movegen][rook]") {
    Board board("7k/8/8/8/3R4/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 3, 3) == 14);
}

TEST_CASE("Rook blocked by own piece", "[movegen][rook]") {
    Board board("7k/8/8/8/3R1P2/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 3, 3, 3, 4));
    REQUIRE_FALSE(has_move(moves, 3, 3, 3, 5));
    REQUIRE_FALSE(has_move(moves, 3, 3, 3, 6));
}

// ===== QUEEN TESTS =====

TEST_CASE("Queen moves on empty board", "[movegen][queen]") {
    Board board("7k/8/8/8/3Q4/8/8/1K6 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 3, 3) == 27);
}

// ===== KING TESTS =====

TEST_CASE("King moves from center", "[movegen][king]") {
    Board board("7k/8/8/8/3K4/8/8/8 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 3, 3) == 8);
}

TEST_CASE("King moves from corner", "[movegen][king]") {
    Board board("7k/8/8/8/8/8/8/K7 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 0, 0) == 3);
}

TEST_CASE("King cannot capture own piece", "[movegen][king]") {
    Board board("7k/8/8/8/3K4/3P4/8/8 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 3, 3, 2, 3));
}

TEST_CASE("Kingside castling white", "[movegen][king][castling]") {
    Board board("7k/8/8/8/8/8/8/R3K2R w KQ - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 0, 4, 0, 6));
}

TEST_CASE("Queenside castling white", "[movegen][king][castling]") {
    Board board("7k/8/8/8/8/8/8/R3K2R w KQ - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 0, 4, 0, 2));
}

TEST_CASE("Castling blocked by piece in between", "[movegen][king][castling]") {
    Board board("7k/8/8/8/8/8/8/R2NK2R w KQ - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 0, 4, 0, 2));
    REQUIRE(has_move(moves, 0, 4, 0, 6));
}

TEST_CASE("Cannot castle out of check", "[movegen][king][castling]") {
    Board board("4r2k/8/8/8/8/8/8/R3K2R w KQ - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 0, 4, 0, 6));
    REQUIRE_FALSE(has_move(moves, 0, 4, 0, 2));
}

TEST_CASE("Cannot castle through check", "[movegen][king][castling]") {
    Board board("5r1k/8/8/8/8/8/8/R3K2R w KQ - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE_FALSE(has_move(moves, 0, 4, 0, 6));
}

TEST_CASE("Black castling", "[movegen][king][castling]") {
    Board board("r3k2r/8/8/8/8/8/8/K7 b kq - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(has_move(moves, 7, 4, 7, 6));
    REQUIRE(has_move(moves, 7, 4, 7, 2));
}

// ===== LEGAL MOVE FILTERING =====

TEST_CASE("Pinned piece cannot move off pin ray", "[movegen][legal]") {
    Board board("4r2k/8/8/8/8/8/4B3/4K3 w - - 0 1");
    auto moves = board.generate_legal_moves();
    REQUIRE(count_from(moves, 1, 4) == 0);
}

TEST_CASE("Must block or evade check", "[movegen][legal]") {
    Board board("4r2k/8/8/8/8/8/8/4K3 w - - 0 1");
    auto moves = board.generate_legal_moves();
    for (const auto& m : moves) {
        REQUIRE(sq_row(m.from_sq) == 0);
        REQUIRE(sq_col(m.from_sq) == 4);
        REQUIRE_FALSE(sq_col(m.to_sq) == 4);
    }
}

TEST_CASE("Starting position has 20 legal moves", "[movegen][legal]") {
    Board board;
    auto moves = board.generate_legal_moves();
    REQUIRE(moves.size() == 20);
}

// ===== MAKE MOVE =====

TEST_CASE("Make move updates board", "[movegen][make_move]") {
    Board board;
    Move m{sq(1, 4), sq(3, 4)};  // e2e4
    board.make_move(m);

    REQUIRE(board.piece_at(3, 4) == Piece::WhitePawn);
    REQUIRE(board.piece_at(1, 4) == Piece::None);
    REQUIRE(board.side_to_move() == Color::Black);
}

TEST_CASE("Make move en passant captures pawn", "[movegen][make_move]") {
    Board board("7k/8/8/3pP3/8/8/8/K7 w - d6 0 1");
    Move m{sq(4, 4), sq(5, 3)};  // e5xd6 en passant
    board.make_move(m);

    REQUIRE(board.piece_at(5, 3) == Piece::WhitePawn);
    REQUIRE(board.piece_at(4, 3) == Piece::None);
    REQUIRE(board.piece_at(4, 4) == Piece::None);
}

TEST_CASE("Make move castling moves rook", "[movegen][make_move]") {
    Board board("7k/8/8/8/8/8/8/R3K2R w KQ - 0 1");
    Move m{sq(0, 4), sq(0, 6)};  // e1g1 kingside castle
    board.make_move(m);

    REQUIRE(board.piece_at(0, 6) == Piece::WhiteKing);
    REQUIRE(board.piece_at(0, 5) == Piece::WhiteRook);
    REQUIRE(board.piece_at(0, 7) == Piece::None);
    REQUIRE(board.piece_at(0, 4) == Piece::None);
}

TEST_CASE("Make move promotion", "[movegen][make_move]") {
    Board board("7k/4P3/8/8/8/8/8/K7 w - - 0 1");
    Move m{sq(6, 4), sq(7, 4), Piece::WhiteQueen};
    board.make_move(m);

    REQUIRE(board.piece_at(7, 4) == Piece::WhiteQueen);
    REQUIRE(board.piece_at(6, 4) == Piece::None);
}

// ===== UCI MOVE PARSING =====

TEST_CASE("Move to UCI string", "[movegen][uci]") {
    Move m{sq(1, 4), sq(3, 4)};
    REQUIRE(m.to_uci() == "e2e4");

    Move promo{sq(6, 4), sq(7, 4), Piece::WhiteQueen};
    REQUIRE(promo.to_uci() == "e7e8q");
}

TEST_CASE("Move from UCI string", "[movegen][uci]") {
    Move m = Move::from_uci("e2e4");
    REQUIRE(m.from_sq == sq(1, 4));
    REQUIRE(m.to_sq == sq(3, 4));

    Move promo = Move::from_uci("e7e8q");
    REQUIRE(sq_row(promo.from_sq) == 6);
    REQUIRE(sq_row(promo.to_sq) == 7);
    REQUIRE(promo.promotion == Piece::WhiteQueen);
}
