// Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
// Licensed under the MIT License. See LICENSE for details.
#include "bitboard.hpp"
#include "zobrist.h"
#include "uci.h"

int main() {
    duchess::init_attack_tables();
    duchess::init_zobrist();
    duchess::uci_loop();
    return 0;
}
