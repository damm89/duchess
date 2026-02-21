cmake_minimum_required(VERSION 3.14)
project(duchess_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# --- Engine library ---
add_library(duchess_engine_lib
    src/bitboard.cpp
    src/board.cpp
    src/eval.cpp
    src/search.cpp
)
target_include_directories(duchess_engine_lib PUBLIC include)

# --- pybind11 Python module ---
find_package(pybind11 REQUIRED)
pybind11_add_module(duchess_engine src/bindings.cpp)
target_link_libraries(duchess_engine PRIVATE duchess_engine_lib)

# --- Catch2 via FetchContent ---
include(FetchContent)
FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.5.2
)
FetchContent_MakeAvailable(Catch2)

# --- Tests ---
add_executable(duchess_tests
    tests/test_bitboard.cpp
    tests/test_board.cpp
    tests/test_eval.cpp
    tests/test_movegen.cpp
    tests/test_search.cpp
)
target_link_libraries(duchess_tests PRIVATE duchess_engine_lib Catch2::Catch2WithMain)

include(CTest)
include(Catch)
catch_discover_tests(duchess_tests)
