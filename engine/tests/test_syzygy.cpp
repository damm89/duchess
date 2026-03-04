#include "board.hpp"
#include "search.hpp"
#include "tbprobe.h"
#include <catch2/catch_test_macros.hpp>

using namespace duchess;

TEST_CASE("Syzygy probe cleanly handles missing files", "[syzygy]") {
  // Try to initialize with a dummy path
  bool ok = tb_init("/this/path/does/not/exist");

  // tb_init returns true if it executes successfully (even if it finds 0 files)
  REQUIRE(ok == true);

  // It should realize no files are present
  REQUIRE(TB_LARGEST == 0);

  // Probing should be a no-op that doesn't crash
  Board board("8/8/8/8/8/8/8/k6K w - - 0 1");
  SearchResult res = search(board, 3);

  // It should evaluate to close to 0 (draw) natively because king vs king is a
  // draw. Positional PSTs might give a slight edge (like +10cp). The key point
  // is it doesn't try to probe and return a mate score.
  REQUIRE(std::abs(res.score) < 100);

  tb_free();
}
