#pragma once

#include <stdint.h>
#include <stddef.h>

/**
 * CC1101 PN9 data-whitening XOR.
 *
 * When CC1101 PKTCTRL0.WHITE_DATA=1 is set on both ends, the radio
 * dewhitens on RX automatically and this function is not needed. Keep
 * it for raw-mode captures (WHITE_DATA=0) and unit-tests against the
 * hex frames in the repo README.
 *
 * LFSR: 9-bit, polynomial x^9 + x^5 + 1, seed 0x1FF. Applies XOR in
 * place.
 */
void pn9_dewhiten(uint8_t* data, size_t len);
