#!/usr/bin/env python3
"""Parse the two 24-byte-record tables in the flash config header.

Structure of each 24-byte record (inferred from lining up known animation
sizes/offsets):
  - 0-15  name (null-terminated ASCII, remainder padded with 0x00)
  - 16-19 size (little-endian u32)
  - 20-23 offset (little-endian u32) into the flash

Table 1 (5 entries starting at 0x0081)  → maps to 5 WAVs, hypothesis
Table 2 (11 entries starting at 0x0355) → maps to 11 animation JSONs, confirmed
"""

import struct
import sys
from pathlib import Path

FLASH = Path(__file__).parent.parent / "teardown" / "mother" / "flash-fw398.bin"

RECORD = 24
NAME_LEN = 16


def parse_table(data: bytes, label: str, table_start: int, count: int) -> None:
    print(f"# {label}  (24-byte records, start=0x{table_start:04x}, {count} entries)\n")
    print(f"  {'name':<20s}  {'size':>10s}  {'offset':>10s}  {'points to':<40s}")
    for i in range(count):
        rec = data[table_start + i * RECORD:table_start + (i + 1) * RECORD]
        name = rec[:NAME_LEN].split(b"\x00")[0].decode("ascii", "replace")
        size, offset = struct.unpack_from("<II", rec, NAME_LEN)
        # What does the offset actually point to?
        target = data[offset:offset + 24]
        preview = target[:16].decode("ascii", "replace") if all(0x20 <= b < 0x7f or b == 0 for b in target[:16]) else target[:8].hex(" ")
        print(f"  {name:<20s}  {size:>10,d}  0x{offset:08x}  {preview!r}")


def main():
    data = FLASH.read_bytes()
    parse_table(data, "Table 1 — hypothesis: name → WAV sound", 0x0081, 5)
    print()
    parse_table(data, "Table 2 — confirmed: name → animation JSON", 0x0355, 11)


if __name__ == "__main__":
    main()
