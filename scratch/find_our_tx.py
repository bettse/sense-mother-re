#!/usr/bin/env python3
"""Scan a rtl_433 hits.json for frames matching our Flipper AP's on-air TX.

Our test-TX signature (build_join_reply → CAFEF00D):
    DST = CA FE F0 0D
    SRC = DE AD BE EF
Real Join-reply TX to a Cookie also uses SRC = DE AD BE EF.

Prints matching lines with their timestamp + dewhitened hex.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten

AP_SRC = bytes.fromhex("deadbeef")
TEST_DST = bytes.fromhex("cafef00d")


def main():
    hits = sys.argv[1] if len(sys.argv) > 1 else "/tmp/cookie_hits.json"
    matches = 0
    total = 0
    for line in open(hits):
        try:
            j = json.loads(line)
        except Exception:
            continue
        rows = j.get("rows", [])
        if not rows:
            continue
        data = rows[0].get("data", "")
        if data.startswith("d391"):
            data = data[4:]
        if len(data) % 2:
            continue
        raw = bytes.fromhex(data)
        clean = dewhiten(raw)
        total += 1
        # SimpliciTI: LEN | DST(4) | SRC(4) | ...
        if len(clean) < 9:
            continue
        dst = clean[1:5]
        src = clean[5:9]
        if src == AP_SRC or dst == TEST_DST:
            matches += 1
            t = j.get("time", "?")
            port = clean[9] & 0x3F if len(clean) > 9 else -1
            print(f"  {t}  len={clean[0]}  dst={dst.hex()}  src={src.hex()}  port={port}")
            print(f"    raw dewhitened: {clean.hex()}")
    print(f"\nscanned {total} frames, {matches} match our AP signature")


if __name__ == "__main__":
    main()
