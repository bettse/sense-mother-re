#!/usr/bin/env python3
"""Analyze an rtl_433 capture of Mother-powered airtime.

Groups frames by (src, dst, port) and tags direction: sender-type from
DEVINFO tells us End Device (0) vs Range Extender (1) vs Access Point
(2). Real Mother traffic shows up as sender=2 with dst != FFFFFFFF
(unicast) or dst = FFFFFFFF (broadcast). Any port we haven't seen from
Cookies before (i.e. not 3 or 7) is the sen.se-specific data channel.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten

SENDER_NAMES = {0: "ED", 1: "RE", 2: "AP", 3: "res"}


def parse_line(line):
    try:
        j = json.loads(line)
    except Exception:
        return None
    rows = j.get("rows", [])
    if not rows:
        return None
    data = rows[0].get("data", "")
    if data.startswith("d391"):
        data = data[4:]
    if len(data) % 2:
        data = data[:-1]
    try:
        raw = bytes.fromhex(data)
    except ValueError:
        return None
    clean = dewhiten(raw)
    if len(clean) < 12:
        return None
    length = clean[0]
    if length < 10 or length + 1 > len(clean):
        return None
    return {
        "time": j.get("time", "?"),
        "length": length,
        "dst": clean[1:5].hex(),
        "src": clean[5:9].hex(),
        "port_byte": clean[9],
        "port": clean[9] & 0x3F,
        "fwd": (clean[9] >> 7) & 1,
        "enc": (clean[9] >> 6) & 1,
        "devinfo": clean[10],
        "sender": (clean[10] >> 4) & 3,
        "hop": clean[10] & 7,
        "payload": clean[11 : length + 1].hex(),
        "full": clean.hex(),
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mother_hits.json"
    frames = [f for f in (parse_line(l) for l in open(path)) if f]
    print(f"# {len(frames)} frames parsed from {path}\n")

    # Group by (src, dst, port)
    groups = defaultdict(list)
    for f in frames:
        key = (f["src"], f["dst"], f["port"])
        groups[key].append(f)

    print(f"# {len(groups)} distinct (src, dst, port) triples\n")

    # Sort by whether it's AP-originated (interesting)
    def key_sort(item):
        (src, dst, port), _ = item
        sample = _[0]
        return (
            -sample["sender"],
            0 if dst == "ffffffff" else 1,
            port,
            src,
        )

    for (src, dst, port), fs in sorted(groups.items(), key=key_sort):
        sample = fs[0]
        sender = SENDER_NAMES[sample["sender"]]
        broadcast = " (BCAST)" if dst == "ffffffff" else ""
        print(
            f"  src={src} → dst={dst}{broadcast}  port={port}  sender={sender}  count={len(fs)}"
        )
        # First frame's payload (up to 32 hex chars)
        for f in fs[:2]:
            print(f"    {f['time']}  payload={f['payload'][:64]}")
        if len(fs) > 2:
            print(f"    ... {len(fs) - 2} more")
        print()


if __name__ == "__main__":
    main()
