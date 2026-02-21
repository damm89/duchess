#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "bitboard.hpp"
#include "board.hpp"
#include "eval.hpp"
#include "search.hpp"

namespace py = pybind11;
using namespace duchess;

PYBIND11_MODULE(duchess_engine, m) {
    m.doc() = "Duchess chess engine — C++ core with Python bindings";

    // Ensure attack tables are initialised on import
    init_attack_tables();

    // --- Piece enum ---
    py::enum_<Piece>(m, "Piece")
        .value("NONE",         Piece::None)
        .value("WHITE_PAWN",   Piece::WhitePawn)
        .value("WHITE_KNIGHT", Piece::WhiteKnight)
        .value("WHITE_BISHOP", Piece::WhiteBishop)
        .value("WHITE_ROOK",   Piece::WhiteRook)
        .value("WHITE_QUEEN",  Piece::WhiteQueen)
        .value("WHITE_KING",   Piece::WhiteKing)
        .value("BLACK_PAWN",   Piece::BlackPawn)
        .value("BLACK_KNIGHT", Piece::BlackKnight)
        .value("BLACK_BISHOP", Piece::BlackBishop)
        .value("BLACK_ROOK",   Piece::BlackRook)
        .value("BLACK_QUEEN",  Piece::BlackQueen)
        .value("BLACK_KING",   Piece::BlackKing)
        .export_values();

    // --- Color enum ---
    py::enum_<Color>(m, "Color")
        .value("WHITE", Color::White)
        .value("BLACK", Color::Black)
        .export_values();

    // --- Move ---
    py::class_<Move>(m, "Move")
        .def(py::init<>())
        .def_readwrite("from_sq",   &Move::from_sq)
        .def_readwrite("to_sq",     &Move::to_sq)
        .def_readwrite("promotion", &Move::promotion)
        .def("to_uci",  &Move::to_uci)
        .def_static("from_uci", &Move::from_uci)
        .def("__repr__", [](const Move& m) {
            return "Move('" + m.to_uci() + "')";
        });

    // --- Board ---
    py::class_<Board>(m, "Board")
        .def(py::init<>())
        .def(py::init<const std::string&>())
        .def("to_fen",              &Board::to_fen)
        .def("side_to_move",        &Board::side_to_move)
        .def("piece_at",            &Board::piece_at)
        .def("piece_at_sq",         &Board::piece_at_sq)
        .def("generate_legal_moves",&Board::generate_legal_moves)
        .def("make_move",           &Board::make_move)
        .def("is_attacked",         &Board::is_attacked)
        .def("__repr__", [](const Board& b) {
            return "Board('" + b.to_fen() + "')";
        });

    // --- SearchResult ---
    py::class_<SearchResult>(m, "SearchResult")
        .def(py::init<>())
        .def_readwrite("best_move", &SearchResult::best_move)
        .def_readwrite("score",     &SearchResult::score)
        .def_readwrite("nodes",     &SearchResult::nodes)
        .def_readwrite("depth",     &SearchResult::depth);

    // --- Free functions ---
    m.def("search",       &search,       "Search position to given depth",
          py::arg("board"), py::arg("depth"));
    m.def("search_timed", &search_timed, "Iterative deepening search with time limit (ms)",
          py::arg("board"), py::arg("time_limit_ms"));
    m.def("evaluate",     &evaluate,     "Evaluate position from side-to-move perspective",
          py::arg("board"));
    m.def("is_checkmate", &is_checkmate, "Check if position is checkmate",
          py::arg("board"));
    m.def("is_stalemate", &is_stalemate, "Check if position is stalemate",
          py::arg("board"));
}
