#!/usr/bin/env python3
"""Print contiguous non-FF regions in the flash dump.

The extractor grabbed config + animations + WAVs. This finds anything
in-between that we might have skipped.
"""

from pathlib import Path

FLASH = Path(__file__).parent.parent / "teardown" / "mother" / "flash-fw398.bin"
GAP_TOLERANCE = 256  # collapse FF gaps shorter than this into the region


def main():
    data = FLASH.read_bytes()
    regions = []
    in_region = False
    start = 0
    ff_run = 0
    for i, b in enumerate(data):
        if b != 0xFF:
            if not in_region:
                start = i
                in_region = True
            ff_run = 0
        else:
            ff_run += 1
            if in_region and ff_run > GAP_TOLERANCE:
                regions.append((start, i - ff_run + 1))
                in_region = False
    if in_region:
        regions.append((start, len(data)))

    print(f"# {len(regions)} contiguous non-FF regions (gaps <= {GAP_TOLERANCE}B merged)\n")
    print(f"  {'start':>10s}  {'end':>10s}  {'size':>10s}  first 24B")
    for start, end in regions:
        first24 = data[start:start + 24]
        preview = first24.hex(" ")
        print(f"  0x{start:08x}  0x{end:08x}  {end - start:>10,}  {preview}")


if __name__ == "__main__":
    main()
