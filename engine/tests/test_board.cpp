#include <catch2/catch_test_macros.hpp>
#include "board.hpp"

using namespace duchess;

struct InitTables {
    InitTables() { init_attack_tables(); }
};
static InitTables _init;

TEST_CASE("Board default constructor sets up starting position", "[board]") {
    Board board;

    // White pieces - back rank
    REQUIRE(board.piece_at(0, 0) == Piece::WhiteRook);
    REQUIRE(board.piece_at(0, 1) == Piece::WhiteKnight);
    REQUIRE(board.piece_at(0, 2) == Piece::WhiteBishop);
    REQUIRE(board.piece_at(0, 3) == Piece::WhiteQueen);
    REQUIRE(board.piece_at(0, 4) == Piece::WhiteKing);
    REQUIRE(board.piece_at(0, 5) == Piece::WhiteBishop);
    REQUIRE(board.piece_at(0, 6) == Piece::WhiteKnight);
    REQUIRE(board.piece_at(0, 7) == Piece::WhiteRook);

    // White pawns
    for (int col = 0; col < 8; ++col)
        REQUIRE(board.piece_at(1, col) == Piece::WhitePawn);

    // Empty middle
    for (int row = 2; row < 6; ++row)
        for (int col = 0; col < 8; ++col)
            REQUIRE(board.piece_at(row, col) == Piece::None);

    // Black pawns
    for (int col = 0; col < 8; ++col)
        REQUIRE(board.piece_at(6, col) == Piece::BlackPawn);

    // Black pieces - back rank
    REQUIRE(board.piece_at(7, 0) == Piece::BlackRook);
    REQUIRE(board.piece_at(7, 1) == Piece::BlackKnight);
    REQUIRE(board.piece_at(7, 2) == Piece::BlackBishop);
    REQUIRE(board.piece_at(7, 3) == Piece::BlackQueen);
    REQUIRE(board.piece_at(7, 4) == Piece::BlackKing);
    REQUIRE(board.piece_at(7, 5) == Piece::BlackBishop);
    REQUIRE(board.piece_at(7, 6) == Piece::BlackKnight);
    REQUIRE(board.piece_at(7, 7) == Piece::BlackRook);
}

TEST_CASE("Board starts with white to move", "[board]") {
    Board board;
    REQUIRE(board.side_to_move() == Color::White);
}

TEST_CASE("Board FEN for starting position", "[board][fen]") {
    Board board;
    REQUIRE(board.to_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
}

TEST_CASE("Board from FEN string", "[board][fen]") {
    Board board("rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2");

    REQUIRE(board.piece_at(3, 4) == Piece::WhitePawn);   // e4
    REQUIRE(board.piece_at(4, 2) == Piece::BlackPawn);    // c5
    REQUIRE(board.piece_at(1, 4) == Piece::None);         // e2 empty
    REQUIRE(board.piece_at(6, 2) == Piece::None);         // c7 empty
    REQUIRE(board.side_to_move() == Color::White);
}

TEST_CASE("Board FEN round-trip", "[board][fen]") {
    std::string fen = "r1bqkb1r/pppppppp/2n2n2/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3";
    Board board(fen);
    REQUIRE(board.to_fen() == fen);
}

TEST_CASE("Board set and get piece", "[board]") {
    Board board("8/8/8/8/8/8/8/8 w - - 0 1");

    board.set_piece(3, 4, Piece::WhiteQueen);
    REQUIRE(board.piece_at(3, 4) == Piece::WhiteQueen);

    board.set_piece(3, 4, Piece::None);
    REQUIRE(board.piece_at(3, 4) == Piece::None);
}
