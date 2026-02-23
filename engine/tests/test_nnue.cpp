#include <catch2/catch_test_macros.hpp>
#include "board.hpp"
#include "nnue.h"
#include "eval.hpp"
#include <vector>

using namespace duchess;

TEST_CASE("NNUE Incremental Updates", "[nnue]") {
    // Requires the user to run the python training script and put the .bin in the proper path
    // For test reliability, we assume it's loaded if the file exists, or we skip if not.
    bool loaded = nnue::load_model("../../nnue/duchess_nnue.bin");
    if (!loaded) loaded = nnue::load_model("../nnue/duchess_nnue.bin");
    
    // If the model isn't built yet, we skip the test silently or just return.
    if (!loaded) {
        SUCCEED("Skipping NNUE test because duchess_nnue.bin is not found.");
        return;
    }

    Board incremental("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    auto moves = incremental.generate_legal_moves();

    for (const auto& m : moves) {
        Board test_board = incremental; 
        test_board.make_move(m);

        // test_board has the accumulator updated incrementally
        // Let's create a fresh board from its FEN and compare
        Board fresh(test_board.to_fen());

        const nnue::Accumulator* acc_incr = test_board.get_accumulator();
        const nnue::Accumulator* acc_fresh = fresh.get_accumulator();

        for (int i = 0; i < nnue::LAYER1_SIZE; ++i) {
            REQUIRE(acc_incr->white[i] == acc_fresh->white[i]);
            REQUIRE(acc_incr->black[i] == acc_fresh->black[i]);
        }
    }
}
