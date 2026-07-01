#!/usr/bin/env python3
"""Read rtl_433 cookie-decoder JSON output, group frames by byte 0 (frame
type), and report which byte positions are constant vs which vary within
each group.

Per-frame-type constants are the candidates for device ID, accelerometer
(while stationary), and temperature (over a short window). Per-frame-type
variables are likely sequence counter and CRC.

Usage:  analyze_frames.py <hits.json> [<hits.json> ...]
"""
import sys, json, os
from collections import defaultdict, Counter

def load_frames(path):
    frames = []
    for line in open(path):
        line = line.strip()
        if not line: continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows = r.get("rows", [])
        if not rows: continue
        data = rows[0].get("data", "")
        len_bits = rows[0].get("len")
        # decoded data starts with the matched sync 'd391'; strip it
        if data.startswith("d391"):
            data = data[4:]
        # hex must be even
        if len(data) % 2: data = data[:-1]
        b = bytes.fromhex(data)
        frames.append({"time": r.get("time"), "rssi": r.get("rssi"),
                       "snr": r.get("snr"), "bytes": b, "len_bits": len_bits})
    return frames

def summarize(frames, label=""):
    print(f"\n=== {label} ({len(frames)} frames) ===")
    if not frames: return
    by_type = defaultdict(list)
    for f in frames:
        if len(f["bytes"]) < 1: continue
        by_type[f["bytes"][0]].append(f)

    for t, group in sorted(by_type.items()):
        print(f"\n--- byte 0 = 0x{t:02x}  ({len(group)} frames) ---")
        n = min(len(f["bytes"]) for f in group)
        print("    pos:   " + " ".join(f"{i:>2}" for i in range(n)))
        # show every frame, then the per-column profile
        for f in group:
            ts = f["time"].split()[1] if f["time"] else "?"
            print(f"    {ts}  " + " ".join(f"{b:02x}" for b in f["bytes"][:n]))
        print("    " + "-" * (8 + 3*n))
        const_line = []
        notes = []
        for i in range(n):
            col = [f["bytes"][i] for f in group]
            c = Counter(col)
            if len(c) == 1:
                const_line.append(f"{col[0]:02x}")
            else:
                const_line.append("..")
                vals = ", ".join(f"0x{v:02x}×{k}" for v,k in c.most_common())
                notes.append(f"      pos {i}:  {vals}")
        print("    CONST  " + " ".join(const_line))
        for n_ in notes:
            print(n_)

def main():
    paths = sys.argv[1:] or ["captures/awesome-you-long/hits.json"]
    for p in paths:
        frames = load_frames(p)
        label = p
        summarize(frames, label)

if __name__ == "__main__":
    main()
