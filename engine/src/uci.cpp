#include "uci.h"
#include "board.hpp"
#include "search.hpp"
#include "eval.hpp"
#include "perft.h"
#include "tt.h"
#include "polyglot.h"
#include <atomic>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace duchess {

static Board board;
static std::atomic<bool> stop_flag{false};
static std::vector<std::thread> search_threads;
static int num_threads = 1;
static bool own_book = false;
static OpeningBook book;

static std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> tokens;
    std::istringstream iss(s);
    std::string tok;
    while (iss >> tok) tokens.push_back(tok);
    return tokens;
}

static void handle_position(const std::vector<std::string>& tokens) {
    size_t move_idx = 0;

    if (tokens.size() < 2) return;

    if (tokens[1] == "startpos") {
        board = Board();
        move_idx = 2;
    } else if (tokens[1] == "fen") {
        std::string fen;
        size_t i = 2;
        while (i < tokens.size() && tokens[i] != "moves") {
            if (!fen.empty()) fen += ' ';
            fen += tokens[i];
            ++i;
        }
        board = Board(fen);
        move_idx = i;
    }

    if (move_idx < tokens.size() && tokens[move_idx] == "moves") {
        for (size_t i = move_idx + 1; i < tokens.size(); ++i) {
            Move m = Move::from_uci(tokens[i]);
            board.make_move(m);
        }
    }
}

static void handle_go(const std::vector<std::string>& tokens) {
    // Handle "go perft <depth>"
    if (tokens.size() >= 3 && tokens[1] == "perft") {
        int depth = std::stoi(tokens[2]);
        perft_divide(board, depth);
        return;
    }

    // Opening book lookup — instant reply if in book
    if (own_book && book.is_loaded()) {
        Move book_move;
        if (book.pick_move(board, book_move)) {
            std::cout << "info depth 0 score cp 0 nodes 0 time 0 pv "
                      << book_move.to_uci() << std::endl;
            std::cout << "bestmove " << book_move.to_uci() << std::endl;
            return;
        }
    }

    int time_limit_ms = 0;
    int max_depth = 64;

    // Parse go parameters
    for (size_t i = 1; i < tokens.size(); ++i) {
        if (tokens[i] == "depth" && i + 1 < tokens.size()) {
            max_depth = std::stoi(tokens[i + 1]);
            ++i;
        } else if (tokens[i] == "movetime" && i + 1 < tokens.size()) {
            time_limit_ms = std::stoi(tokens[i + 1]);
            ++i;
        } else if (tokens[i] == "wtime" && i + 1 < tokens.size()) {
            if (board.side_to_move() == Color::White) {
                // Use ~1/30th of remaining time as move time
                int wtime = std::stoi(tokens[i + 1]);
                if (time_limit_ms == 0) time_limit_ms = std::max(100, wtime / 30);
            }
            ++i;
        } else if (tokens[i] == "btime" && i + 1 < tokens.size()) {
            if (board.side_to_move() == Color::Black) {
                int btime = std::stoi(tokens[i + 1]);
                if (time_limit_ms == 0) time_limit_ms = std::max(100, btime / 30);
            }
            ++i;
        } else if (tokens[i] == "winc" || tokens[i] == "binc" ||
                   tokens[i] == "movestogo") {
            ++i; // skip value
        } else if (tokens[i] == "infinite") {
            time_limit_ms = 0;
            max_depth = 64;
        }
    }

    // If no time control at all, default to 1 second
    if (time_limit_ms == 0 && max_depth == 64) {
        time_limit_ms = 1000;
    }

    // Join previous search threads if still running
    if (!search_threads.empty()) {
        stop_flag.store(true);
        for (auto& t : search_threads) {
            if (t.joinable()) t.join();
        }
        search_threads.clear();
    }

    stop_flag.store(false);

    // Take a copy of the board for the search threads
    Board search_board = board;
    int threads_to_launch = num_threads;

    // Thread 0: main search thread (prints info and bestmove)
    search_threads.emplace_back([search_board, time_limit_ms, max_depth]() {
        auto info_cb = [](const SearchResult& r, int elapsed_ms) {
            int nps = elapsed_ms > 0 ? static_cast<int>(
                static_cast<long long>(r.nodes) * 1000 / elapsed_ms) : 0;

            std::cout << "info depth " << r.depth
                      << " score cp " << r.score
                      << " nodes " << r.nodes
                      << " time " << elapsed_ms
                      << " nps " << nps
                      << " pv " << r.best_move.to_uci()
                      << std::endl;
        };

        SearchResult result = search_uci(
            search_board, stop_flag, time_limit_ms, max_depth, info_cb, 0);

        std::cout << "bestmove " << result.best_move.to_uci() << std::endl;
    });

    // Helper threads: silently search and populate TT
    for (int i = 1; i < threads_to_launch; ++i) {
        search_threads.emplace_back([search_board, max_depth, i]() {
            search_uci(search_board, stop_flag, 0, max_depth, nullptr, i);
        });
    }
}

static char piece_char(Piece p) {
    switch (p) {
        case Piece::WhitePawn:   return 'P';
        case Piece::WhiteKnight: return 'N';
        case Piece::WhiteBishop: return 'B';
        case Piece::WhiteRook:   return 'R';
        case Piece::WhiteQueen:  return 'Q';
        case Piece::WhiteKing:   return 'K';
        case Piece::BlackPawn:   return 'p';
        case Piece::BlackKnight: return 'n';
        case Piece::BlackBishop: return 'b';
        case Piece::BlackRook:   return 'r';
        case Piece::BlackQueen:  return 'q';
        case Piece::BlackKing:   return 'k';
        default: return '.';
    }
}

static void handle_debug_print() {
    std::cout << std::endl;
    for (int rank = 7; rank >= 0; --rank) {
        std::cout << " " << (rank + 1) << "  ";
        for (int file = 0; file < 8; ++file) {
            int sq = rank * 8 + file;
            std::cout << piece_char(board.piece_at_sq(sq)) << ' ';
        }
        std::cout << std::endl;
    }
    std::cout << "    a b c d e f g h" << std::endl;
    std::cout << std::endl;
    std::cout << "Fen: " << board.to_fen() << std::endl;
    std::cout << "Side: " << (board.side_to_move() == Color::White ? "white" : "black") << std::endl;
    std::cout << std::endl;
}

void uci_loop() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        auto tokens = split(line);
        if (tokens.empty()) continue;

        const auto& cmd = tokens[0];

        if (cmd == "uci") {
            std::cout << "id name Duchess" << std::endl;
            std::cout << "id author Duchess Team" << std::endl;
            std::cout << "option name Hash type spin default 16 min 1 max 1024" << std::endl;
            std::cout << "option name Threads type spin default 1 min 1 max 128" << std::endl;
            std::cout << "option name OwnBook type check default false" << std::endl;
            std::cout << "option name BookFile type string default <empty>" << std::endl;
            std::cout << "uciok" << std::endl;
        } else if (cmd == "isready") {
            // Wait for search to finish before responding
            for (auto& t : search_threads) {
                if (t.joinable()) t.join();
            }
            search_threads.clear();
            std::cout << "readyok" << std::endl;
        } else if (cmd == "setoption") {
            if (tokens.size() >= 5 && tokens[1] == "name" && tokens[3] == "value") {
                if (tokens[2] == "Hash") {
                    int mb = std::stoi(tokens[4]);
                    if (mb < 1) mb = 1;
                    if (mb > 1024) mb = 1024;
                    tt.resize(static_cast<size_t>(mb));
                } else if (tokens[2] == "Threads") {
                    num_threads = std::max(1, std::stoi(tokens[4]));
                } else if (tokens[2] == "OwnBook") {
                    own_book = (tokens[4] == "true");
                } else if (tokens[2] == "BookFile") {
                    if (book.load(tokens[4])) {
                        own_book = true;
                    }
                }
            }
        } else if (cmd == "ucinewgame") {
            stop_flag.store(true);
            for (auto& t : search_threads) {
                if (t.joinable()) t.join();
            }
            search_threads.clear();
            board = Board();
            tt.clear();
        } else if (cmd == "position") {
            handle_position(tokens);
        } else if (cmd == "go") {
            handle_go(tokens);
        } else if (cmd == "stop") {
            stop_flag.store(true);
            for (auto& t : search_threads) {
                if (t.joinable()) t.join();
            }
            search_threads.clear();
        } else if (cmd == "legalmoves") {
            auto moves = board.generate_legal_moves();
            std::cout << "legalmoves";
            for (const auto& m : moves) {
                std::cout << " " << m.to_uci();
            }
            std::cout << std::endl;
        } else if (cmd == "gamestate") {
            auto moves = board.generate_legal_moves();
            if (moves.empty()) {
                if (is_checkmate(board)) {
                    std::cout << "gamestate checkmate" << std::endl;
                } else {
                    std::cout << "gamestate stalemate" << std::endl;
                }
            } else {
                std::cout << "gamestate playing" << std::endl;
            }
        } else if (cmd == "fen") {
            std::cout << "fen " << board.to_fen() << std::endl;
        } else if (cmd == "piece") {
            // piece <sq> — returns piece at square (0-63)
            if (tokens.size() >= 2) {
                int sq = std::stoi(tokens[1]);
                std::cout << "piece " << sq << " " << static_cast<int>(board.piece_at_sq(sq)) << std::endl;
            }
        } else if (cmd == "pieces") {
            // Output all 64 squares as integers on one line
            std::cout << "pieces";
            for (int sq = 0; sq < 64; ++sq) {
                std::cout << " " << static_cast<int>(board.piece_at_sq(sq));
            }
            std::cout << std::endl;
        } else if (cmd == "side") {
            std::cout << "side " << (board.side_to_move() == Color::White ? "white" : "black") << std::endl;
        } else if (cmd == "isattacked") {
            // isattacked <sq> <color: white|black>
            if (tokens.size() >= 3) {
                int sq = std::stoi(tokens[1]);
                Color c = (tokens[2] == "white") ? Color::White : Color::Black;
                std::cout << "isattacked " << (board.is_attacked(sq, c) ? "true" : "false") << std::endl;
            }
        } else if (cmd == "eval") {
            int score = evaluate(board);
            auto moves = board.generate_legal_moves();
            if (moves.empty() && is_checkmate(board)) {
                std::cout << "eval mate 0" << std::endl;
            } else {
                std::cout << "eval cp " << score << std::endl;
            }
        } else if (cmd == "d") {
            handle_debug_print();
        } else if (cmd == "quit") {
            stop_flag.store(true);
            for (auto& t : search_threads) {
                if (t.joinable()) t.join();
            }
            search_threads.clear();
            break;
        }
    }
}

}  // namespace duchess
