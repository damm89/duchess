cmake_minimum_required(VERSION 3.14)
project(duchess_engine LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(DUCHESS_NATIVE_ARCH "Use -march=native for local CPU optimizations" ON)
if (DUCHESS_NATIVE_ARCH AND NOT MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native")
elseif (MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /O2")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} /O2 /experimental:c11atomics")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3")
endif()

# --- Engine library ---
add_library(duchess_engine_lib
    src/bitboard.cpp
    src/board.cpp
    src/eval.cpp
    src/search.cpp
    src/perft.cpp
    src/zobrist.cpp
    src/tt.cpp
    src/polyglot.cpp
    src/nnue.cpp
    fathom/src/tbprobe.c
)
target_include_directories(duchess_engine_lib PUBLIC include fathom/src)

# --- UCI standalone executable ---
add_executable(duchess_cli src/main.cpp src/uci.cpp)
target_link_libraries(duchess_cli PRIVATE duchess_engine_lib)

# --- pybind11 Python module (optional — skipped in CI builds) ---
option(DUCHESS_BUILD_PYTHON "Build Python bindings via pybind11" ON)
if (DUCHESS_BUILD_PYTHON)
    find_package(pybind11 QUIET)
    if (NOT pybind11_FOUND)
        execute_process(
            COMMAND python -c "import pybind11; print(pybind11.get_cmake_dir())"
            OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
            OUTPUT_STRIP_TRAILING_WHITESPACE
            RESULT_VARIABLE PYBIND11_RESULT
        )
        if (PYBIND11_RESULT EQUAL 0)
            list(APPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKE_DIR}")
            find_package(pybind11 REQUIRED)
        else()
            message(WARNING "pybind11 not found — skipping Python bindings. Install with: pip install pybind11")
            set(DUCHESS_BUILD_PYTHON OFF)
        endif()
    endif()
endif()

if (DUCHESS_BUILD_PYTHON)
    pybind11_add_module(duchess_engine src/bindings.cpp)
    target_link_libraries(duchess_engine PRIVATE duchess_engine_lib)
endif()

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
    tests/test_tt.cpp
    tests/test_polyglot.cpp
    tests/test_syzygy.cpp
    tests/test_nnue.cpp
)
target_link_libraries(duchess_tests PRIVATE duchess_engine_lib Catch2::Catch2WithMain)

include(CTest)
include(Catch)
catch_discover_tests(duchess_tests)
