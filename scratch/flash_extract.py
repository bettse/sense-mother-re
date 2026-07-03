#!/usr/bin/env python3
"""Extract useful files from the Mother's SPI flash dump.

Naming is table-driven: the config header at 0x0000-0x0530 contains two
24-byte-record tables that map state names to (size, offset) pairs.

  Table 1 (0x0081, 5 entries)  → sound name → RIFF/WAV offset
  Table 2 (0x0355, 11 entries) → animation name → JSON blob offset

Record layout (24 bytes):
  0-15   name  (null-terminated ASCII, remainder padded with 0x00)
  16-19  size  (little-endian u32)
  20-23  offset (little-endian u32)

Output layout:
  teardown/mother/flash-extracted/
    config-header.bin          — raw 0x0000..0x1000 config section
    config-header-strings.txt  — printable strings, for grepping
    animations/<state>.json    — one per state name, pretty-printed
    animations/index.txt       — table dump: name → (size, offset)
    audio/<state>.wav          — one per state name
    audio/index.txt            — table dump: name → (size, offset)
"""

import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FLASH = ROOT / "teardown" / "mother" / "flash-fw398.bin"
OUT = ROOT / "teardown" / "mother" / "flash-extracted"

TABLE1_START = 0x0081  # sound table: name → WAV
TABLE1_COUNT = 5
TABLE2_START = 0x0355  # animation table: name → JSON blob
TABLE2_COUNT = 11
RECORD = 24
NAME_LEN = 16


def parse_table(data: bytes, table_start: int, count: int) -> list[tuple[str, int, int]]:
    """Yield (name, size, offset) tuples from a config-header table."""
    entries = []
    for i in range(count):
        rec = data[table_start + i * RECORD:table_start + (i + 1) * RECORD]
        name = rec[:NAME_LEN].split(b"\x00")[0].decode("ascii")
        size, offset = struct.unpack_from("<II", rec, NAME_LEN)
        entries.append((name, size, offset))
    return entries


def extract_config_header(data: bytes) -> None:
    (OUT / "config-header.bin").write_bytes(data[:0x1000])
    strings = re.findall(rb"[\x20-\x7e]{4,}", data[:0x1000])
    (OUT / "config-header-strings.txt").write_text(
        "\n".join(s.decode("ascii") for s in strings) + "\n"
    )


def extract_animations(data: bytes, table: list[tuple[str, int, int]]) -> None:
    anim_dir = OUT / "animations"
    anim_dir.mkdir(exist_ok=True)
    # Clean any stale numeric files from previous extractor version
    for stale in anim_dir.glob("[0-9][0-9].json"):
        stale.unlink()
    index_lines = ["# name → animation JSON (Table 2 at 0x0355)"]
    for name, size, offset in table:
        blob = data[offset:offset + size]
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError as e:
            print(f"  WARN: {name} failed to parse: {e}")
            continue
        (anim_dir / f"{name}.json").write_text(json.dumps(parsed, indent=2) + "\n")
        first_type = parsed[0].get("type", "?") if parsed else "?"
        index_lines.append(f"  {name:<20s}  0x{offset:06x}  {size:>5}B  first_type={first_type}")
    (anim_dir / "index.txt").write_text("\n".join(index_lines) + "\n")
    print(f"animations: {len(table)} JSON blobs extracted")


def extract_audio(data: bytes, table: list[tuple[str, int, int]]) -> None:
    audio_dir = OUT / "audio"
    audio_dir.mkdir(exist_ok=True)
    for stale in audio_dir.glob("[0-9][0-9].wav"):
        stale.unlink()
    index_lines = ["# name → WAV file (Table 1 at 0x0081)"]
    for name, size, offset in table:
        wav_bytes = data[offset:offset + size]
        if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
            print(f"  WARN: {name} at 0x{offset:x} is not a RIFF/WAVE")
            continue
        # Parse fmt chunk for label
        try:
            fmt_off = wav_bytes.index(b"fmt ")
            fmt_tag, channels, samplerate, _, _, bits = \
                struct.unpack_from("<HHIIHH", wav_bytes, fmt_off + 8)
            label = f"{samplerate}Hz {bits}bit {'mono' if channels == 1 else 'stereo'}"
        except Exception:
            label = "?"
        (audio_dir / f"{name}.wav").write_bytes(wav_bytes)
        index_lines.append(f"  {name:<20s}  0x{offset:06x}  {size:>6}B  {label}")
    (audio_dir / "index.txt").write_text("\n".join(index_lines) + "\n")
    print(f"audio: {len(table)} WAV files extracted")


def main():
    if not FLASH.exists():
        sys.exit(f"missing: {FLASH}")
    data = FLASH.read_bytes()
    OUT.mkdir(exist_ok=True)

    sounds = parse_table(data, TABLE1_START, TABLE1_COUNT)
    animations = parse_table(data, TABLE2_START, TABLE2_COUNT)

    extract_config_header(data)
    extract_animations(data, animations)
    extract_audio(data, sounds)


if __name__ == "__main__":
    main()
