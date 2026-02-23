#include "bitboard.hpp"
#include "zobrist.h"
#include "uci.h"

int main() {
    duchess::init_attack_tables();
    duchess::init_zobrist();
    duchess::uci_loop();
    return 0;
}
