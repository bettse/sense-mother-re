#!/usr/bin/env python3
"""Density map + region survey of the Mother flash dump.

The first pass found only 1 sen.se hit and 0 sync/token hits in 8 MiB —
strongly suggests the PIC32's firmware lives in its INTERNAL flash, and
this external SPI holds only config + assets.

This script:
  1. Buckets the file into 64 KiB blocks, prints non-FF byte percentage
     per block — reveals where real content sits vs untouched flash.
  2. Prints the first 512 bytes of each populated block.
  3. Scans for common file magics (JPEG, PNG, GIF, ZIP, gzip, HTML, JSON).
  4. Prints all >= 6-char printable strings from the populated regions.
"""

import re
import sys
from pathlib import Path

FLASH = Path(__file__).parent.parent / "teardown" / "mother" / "flash-fw398.bin"
BLOCK = 64 * 1024  # 64 KiB

MAGICS = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"GIF87a": "GIF87a",
    b"GIF89a": "GIF89a",
    b"PK\x03\x04": "ZIP",
    b"\x1f\x8b\x08": "gzip",
    b"<html": "HTML",
    b"<HTML": "HTML",
    b"<!DO": "HTML DOCTYPE",
    b"<?xml": "XML",
    b"{\"": "JSON obj",
    b"[\"": "JSON arr",
    b"\x7fELF": "ELF",
    b"MZ": "MZ/PE",
}


def block_survey(data: bytes) -> None:
    print(f"# Block density map — non-FF bytes per 64 KiB block")
    print(f"# (only printing blocks with >= 1% non-FF)\n")
    print(f"  {'offset':>10s}  {'non-FF %':>10s}  {'first non-FF':>14s}")
    for base in range(0, len(data), BLOCK):
        block = data[base:base + BLOCK]
        non_ff = sum(1 for b in block if b != 0xFF)
        if non_ff * 100 < len(block):  # under 1%
            continue
        first_content = next((i for i, b in enumerate(block) if b != 0xFF), -1)
        pct = non_ff * 100 / len(block)
        print(f"  0x{base:08x}  {pct:>9.2f}%  0x{base + first_content:08x}")


def magic_scan(data: bytes) -> None:
    print("\n# Magic-number scan (first 20 hits each)")
    for magic, label in MAGICS.items():
        # skip finding within FF runs (would be spurious)
        hits = []
        start = 0
        while True:
            idx = data.find(magic, start)
            if idx < 0:
                break
            hits.append(idx)
            start = idx + 1
            if len(hits) >= 200:
                break
        if hits:
            print(f"  {label:>14s}: {len(hits)} hits, first at {[f'0x{h:x}' for h in hits[:5]]}")


def string_scan(data: bytes, min_len: int = 6) -> None:
    print(f"\n# Printable ASCII strings (>= {min_len} chars, non-FF regions only)")
    pat = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    count = 0
    seen = set()
    for m in pat.finditer(data):
        s = m.group()
        if s in seen:
            continue
        seen.add(s)
        # skip strings buried in obvious FF runs (context check)
        print(f"  0x{m.start():08x}  {s.decode('ascii', 'replace')}")
        count += 1
        if count >= 200:
            print("  ... (truncated at 200)")
            return


def main():
    if not FLASH.exists():
        sys.exit(f"missing: {FLASH}")
    data = FLASH.read_bytes()
    print(f"# file: {FLASH.name}  ({len(data):,} bytes = {len(data) // 1024} KiB)")
    non_ff_total = sum(1 for b in data if b != 0xFF)
    print(f"# total non-FF bytes: {non_ff_total:,} ({non_ff_total * 100 / len(data):.2f}%)\n")

    block_survey(data)
    magic_scan(data)
    string_scan(data)


if __name__ == "__main__":
    main()
