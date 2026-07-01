#!/usr/bin/env python3
"""Run decode_fsk_v2 on every cookie burst, align the post-sync bytes, and
report which positions are constant across captures and which vary.

A column that is identical across N captures is a candidate for a fixed
header (sync extension, length, address, device ID). Columns that vary are
candidates for sequence counters, sensor readings, or CRC."""
import subprocess, re, os, sys
from collections import Counter

def decode(path, rate=99970):
    p = subprocess.run(
        ["python3", os.path.join(os.path.dirname(__file__), "decode_fsk_v2.py"),
         "--rate", str(rate), path],
        capture_output=True, text=True)
    m = re.search(r"sync 0x([0-9a-f]+) \((normal|inverted)\) at bit (\d+): ([0-9a-f]+)", p.stdout)
    if not m:
        return None
    return {"sync_hex": m.group(1), "polarity": m.group(2),
            "bit_offset": int(m.group(3)), "hex": m.group(4)}

def main():
    files = sys.argv[1:] or [
        f"captures/run3/g{i}_915M_2400k.cu8" for i in ("002", "014", "024", "030", "036")
    ]
    base = "/Users/bettse/Downloads/sense-mother-re"
    decoded = []
    for f in files:
        full = os.path.join(base, f) if not os.path.isabs(f) else f
        d = decode(full)
        label = os.path.basename(f).split("_")[0]
        if d is None:
            print(f"{label}: no sync"); continue
        # bytes AFTER the sync word
        sync_bytes = bytes.fromhex(d["sync_hex"])
        full_bytes = bytes.fromhex(d["hex"])
        # strip the matched sync from the front
        if full_bytes.startswith(sync_bytes):
            post = full_bytes[len(sync_bytes):]
        else:
            post = full_bytes
        # also strip a *second* d391 if present (32-bit doubled sync mode)
        if post[:2] == bytes.fromhex(d["sync_hex"]):
            post = post[2:]
            had_double = True
        else:
            had_double = False
        decoded.append((label, had_double, post))

    if not decoded:
        return
    # column-wise alignment
    n = min(len(d[2]) for d in decoded)
    print(f"\nAligned bytes after sync (n={n} bytes):\n")
    header = "       byte:  " + " ".join(f"{i:>2}" for i in range(n))
    print(header)
    for label, dbl, post in decoded:
        flag = "**" if dbl else "  "
        line = "  ".join(f"{b:02x}" for b in post[:n])
        print(f"{label} {flag}    {line}")

    print("\nColumn entropy / dominant value:")
    print("  col  dominant  unique_values  notes")
    for i in range(n):
        col = [d[2][i] for d in decoded]
        c = Counter(col)
        dom_val, dom_cnt = c.most_common(1)[0]
        unique = len(c)
        note = ""
        if dom_cnt == len(decoded): note = "CONSTANT"
        elif unique == 2: note = f"two values: {[hex(v) for v in c]}"
        else: note = "varies"
        print(f"  {i:>3}    0x{dom_val:02x}     {unique}            {note}")

if __name__ == "__main__":
    main()
