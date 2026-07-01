#!/usr/bin/env python3
"""CC1101 PN9 data-whitening XOR.

CC1101's PKTCTRL0.WHITE_DATA=1 (default) XORs the data field (after
length byte, before CRC) with a fixed PN9 keystream. If sen.se left
the default enabled, the bytes we see over the air are pre-whitened
and need this pass before further protocol parsing.

PN9 LFSR: polynomial x^9 + x^5 + 1, seed 0x1FF, 8 bits shifted per byte.

Usage:  cc1101_dewhiten.py <hex> [<hex> ...]
"""
import sys


def pn9_stream(n_bytes):
    """Standard CC1101 PN9 keystream. LFSR = 9 bits, poly = x^9 + x^5 + 1,
    seed = 0x1FF."""
    lfsr = 0x1FF
    out = bytearray()
    for _ in range(n_bytes):
        byte = 0
        for bit_i in range(8):
            # feedback = bit0 XOR bit5 of the 9-bit LFSR
            fb = ((lfsr >> 0) & 1) ^ ((lfsr >> 5) & 1)
            byte |= ((lfsr >> 0) & 1) << bit_i
            lfsr = ((lfsr >> 1) | (fb << 8)) & 0x1FF
        out.append(byte)
    return bytes(out)


def dewhiten(data_bytes):
    ks = pn9_stream(len(data_bytes))
    return bytes(a ^ b for a, b in zip(data_bytes, ks))


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    print(f"# PN9 first 16 bytes: {pn9_stream(16).hex()}")
    for hx in sys.argv[1:]:
        raw = bytes.fromhex(hx.replace(" ", ""))
        clean = dewhiten(raw)
        print(f"whitened:   {raw.hex()}")
        print(f"dewhitened: {clean.hex()}")
        print()


if __name__ == "__main__":
    main()
