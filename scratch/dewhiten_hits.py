#!/usr/bin/env python3
"""Dump every frame in an rtl_433 hits.json, dewhitened, with DST/SRC/port.

Useful for eyeballing what's actually on-air during a capture — including
frames from our own AP that /scratch/find_our_tx.py might reject if the
DST/SRC pattern isn't quite what it expected.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/cookie_hits.json"
    for line in open(path):
        try:
            j = json.loads(line)
        except Exception:
            continue
        rows = j.get("rows", [])
        if not rows:
            continue
        data = rows[0].get("data", "")
        rawlen = rows[0].get("len", 0)
        if data.startswith("d391"):
            data = data[4:]
        if len(data) % 2:
            data = data[:-1]
        raw = bytes.fromhex(data)
        clean = dewhiten(raw)
        if len(clean) < 9:
            print(f"  {rawlen}b too short: {clean.hex()}")
            continue
        length = clean[0]
        dst = clean[1:5].hex()
        src = clean[5:9].hex() if len(clean) >= 9 else "?"
        port_byte = clean[9] if len(clean) >= 10 else 0
        port = port_byte & 0x3F
        fwd = (port_byte >> 7) & 1
        t = j.get("time", "?")
        print(f"  {t}  raw={rawlen}b  LEN={length}  dst={dst}  src={src}  port={port} fwd={fwd}  full={clean.hex()}")


if __name__ == "__main__":
    main()
