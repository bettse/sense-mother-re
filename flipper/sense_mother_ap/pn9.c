#include "pn9.h"

void pn9_dewhiten(uint8_t* data, size_t len) {
    uint16_t lfsr = 0x1FF;
    for(size_t i = 0; i < len; i++) {
        uint8_t ks = 0;
        for(int bit = 0; bit < 8; bit++) {
            uint8_t fb = (lfsr & 1) ^ ((lfsr >> 5) & 1);
            ks |= (lfsr & 1) << bit;
            lfsr = ((lfsr >> 1) | ((uint16_t)fb << 8)) & 0x1FF;
        }
        data[i] ^= ks;
    }
}
