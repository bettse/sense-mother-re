#!/usr/bin/env python3
"""First-pass hunts over the Mother's SPI flash dump.

Looks for:
  1. SimpliciTI Join Token 08 07 06 05
  2. CC1101 sync word D3 91 (and reversed 91 D3)
  3. Known Cookie SRCADDRs (safe song, awesome you, organic macarons)
  4. PIC32 firmware version markers ("398", "Firmware Version", etc.)

Prints byte offsets in hex + short context. Meant to be a triage tool;
follow-up work should promote hits to dedicated parsers.
"""

import sys
from pathlib import Path

FLASH = Path(__file__).parent.parent / "teardown" / "mother" / "flash-fw398.bin"

NEEDLES = {
    "Join Token (08 07 06 05)": bytes.fromhex("08070605"),
    "Sync word (D3 91)": bytes.fromhex("d391"),
    "Sync word reversed (91 D3)": bytes.fromhex("91d3"),
    "SRCADDR safe song (6f ec 16 15)": bytes.fromhex("6fec1615"),
    "SRCADDR awesome you (1f a7 1a 28)": bytes.fromhex("1fa71a28"),
    "SRCADDR organic macarons (1f a8 25 25)": bytes.fromhex("1fa82525"),
}


def find_all(hay: bytes, needle: bytes):
    """Yield every start offset of needle in hay."""
    start = 0
    while True:
        idx = hay.find(needle, start)
        if idx < 0:
            return
        yield idx
        start = idx + 1


def context(hay: bytes, offset: int, nlen: int, pre: int = 8, post: int = 16) -> str:
    lo = max(0, offset - pre)
    hi = min(len(hay), offset + nlen + post)
    excerpt = hay[lo:hi].hex(" ")
    marker_start = (offset - lo) * 3
    marker_end = marker_start + nlen * 3 - 1
    return f"[{excerpt[:marker_start]}<{excerpt[marker_start:marker_end]}>{excerpt[marker_end:]}]"


def main():
    if not FLASH.exists():
        sys.exit(f"missing: {FLASH}")
    data = FLASH.read_bytes()
    print(f"# {FLASH.relative_to(FLASH.parent.parent.parent)}  ({len(data):,} bytes)\n")

    for label, needle in NEEDLES.items():
        hits = list(find_all(data, needle))
        print(f"## {label}: {len(hits)} hits")
        for off in hits[:20]:
            print(f"  0x{off:08x}  {context(data, off, len(needle))}")
        if len(hits) > 20:
            print(f"  ... ({len(hits) - 20} more)")
        print()

    # ASCII "398" and firmware markers
    print("## Firmware version markers")
    for tag in [b"Firmware", b"version", b"Version", b"SENSE", b"sen.se", b"SimpliciTI"]:
        hits = list(find_all(data, tag))
        if hits:
            print(f"  {tag!r}: {len(hits)} hits at {[f'0x{h:x}' for h in hits[:5]]}")


if __name__ == "__main__":
    main()
