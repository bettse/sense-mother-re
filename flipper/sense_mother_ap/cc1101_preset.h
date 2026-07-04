#pragma once

#include <stdint.h>
#include <stddef.h>

/**
 * CC1101 register preset for sen.se Mother / Cookie SimpliciTI PHY.
 *
 *   Band:        915 MHz (US, FCC Part 15.249). Set at runtime via
 *                furi_hal_subghz_set_frequency(915000000).
 *   Modulation:  2-GFSK
 *   Bit rate:    249.94 kbps (DRATE_E=13, DRATE_M=59)     — TI SimpliciTI default
 *   Deviation:   ~127 kHz    (DEVIATN=0x62)
 *   RX BW:       541 kHz     (CHANBW_E=0, CHANBW_M=2)
 *   Sync word:   0xD391      (SYNC1=0xD3, SYNC0=0x91)
 *   Whitening:   PN9 ON      (PKTCTRL0.WHITE_DATA=1) — CC1101 dewhitens on RX
 *   Length:      variable    (PKTCTRL0.LENGTH_CONFIG=01, first byte = length)
 *   CRC:         off in HW   (soft-CRC / raw-log so we don't drop malformed frames)
 *   IOCFG0:      GDO0 asserts on sync-word detected, de-asserts at end-of-packet
 *
 * Values are TI's stock SmartRF preset for SimpliciTI on CC1101 / CC430
 * (see simpliciti/simpliciti-1.1.1-ccs/Components/mrfi/smartrf/CC1101/smartrf_CC1101.h),
 * with WHITE_DATA flipped ON (bit 6 of PKTCTRL0) to match sen.se's actual
 * on-air behavior.
 *
 * Format is Flipper's furi_hal_subghz_load_custom_preset() layout:
 *   [reg, val, reg, val, ..., 0x00, 0x00, pa[0..7]]
 */
// NOTE: furi_hal_subghz_load_custom_preset uses a single-byte terminator
// (`while(preset_data[i])` in furi_hal_subghz.c). This means we can never
// write CC1101 register 0x00 (IOCFG2) via a preset — an entry with reg=0x00
// terminates the loader early and everything after it is silently dropped.
// IOCFG2 default (0x29 = CHIP_RDY) is fine for our use so we don't need it.
static const uint8_t sense_cc1101_preset[] = {
    // GDO0 = sync/EOF strobe (asserts on sync detect, deasserts at EOP)
    0x02 /* IOCFG0  */, 0x06,
    // Packet handling
    0x06 /* PKTLEN   */, 0xFF,
    0x07 /* PKTCTRL1 */, 0x04, // APPEND_STATUS=1, no addr filter
    0x08 /* PKTCTRL0 */, 0x45, // WHITE_DATA=1, PKT_FORMAT=00, CRC_EN=1, LENGTH_CONFIG=01 (var).
                               // Cookies send with CC1101 defaults which include CRC_EN=1,
                               // so they'll reject frames without a valid CCITT CRC. On our
                               // TX side, CRC_EN=1 also auto-appends 2 CRC bytes after the
                               // LEN-declared body. The earlier UNDERFLOW-with-CRC-on issue
                               // was really about the combined-burst FIFO write, not CRC;
                               // split writes (single-byte LEN + burst body) fix both.
    // Sync word 0xD391
    0x04 /* SYNC1    */, 0xD3,
    0x05 /* SYNC0    */, 0x91,
    // IF / offset — TI SmartRF 100 kbps recommendation
    0x0B /* FSCTRL1  */, 0x06,
    0x0C /* FSCTRL0  */, 0x00,
    // Modem: 100 kbps 2-GFSK, 30/32 sync + carrier sense, 4-byte preamble min.
    // Chosen empirically: rtl_433's working flex decoder uses s=10 µs → 100 kbps.
    0x10 /* MDMCFG4  */, 0x8B, // CHANBW_E=2 CHANBW_M=0 (BW=203 kHz), DRATE_E=11
    0x11 /* MDMCFG3  */, 0xF8, // DRATE_M=248 -> 99.98 kbps
    0x12 /* MDMCFG2  */, 0x13, // 2-GFSK, sync mode 30/32 + carrier sense
    0x13 /* MDMCFG1  */, 0x22, // 4-byte preamble, CHANSPC_E=2
    0x14 /* MDMCFG0  */, 0xF8, // CHANSPC_M=0xF8 (unused, single channel)
    // GFSK deviation ~47 kHz (h ≈ 0.94 at 100 kbps)
    0x15 /* DEVIATN  */, 0x47,
    // Main state machine: auto-cal from IDLE, stay in RX after RX (default MCSM1)
    0x18 /* MCSM0    */, 0x18,
    // FOC / BSCFG / AGC — TI recommended defaults for 900 MHz + 100 kbps
    0x19 /* FOCCFG   */, 0x1D,
    0x1A /* BSCFG    */, 0x1C,
    0x1B /* AGCCTRL2 */, 0xC7,
    0x1C /* AGCCTRL1 */, 0x00,
    0x1D /* AGCCTRL0 */, 0xB0,
    // Front-end (from SmartRF defaults)
    0x21 /* FREND1   */, 0xB6,
    0x22 /* FREND0   */, 0x10,
    // FSCAL — TI recommended
    0x23 /* FSCAL3   */, 0xEA,
    0x24 /* FSCAL2   */, 0x2A,
    0x25 /* FSCAL1   */, 0x00,
    0x26 /* FSCAL0   */, 0x1F,
    // TEST — TI recommended for RX at 100 kbps
    0x2C /* TEST2    */, 0x88,
    0x2D /* TEST1    */, 0x31,
    0x2E /* TEST0    */, 0x09,
    0x00, 0x00,
    // PA table — slot 0 only. 0xC0 ~= +10 dBm at 915 MHz. Unused in RX-only phase 1.
    0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};
