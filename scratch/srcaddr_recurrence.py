#!/usr/bin/env python3
"""Check which de-whitened SRCADDRs recur across capture sessions.

A "real" neighbor device (or one of our own Cookies) should appear in
multiple independent captures. A one-off SRCADDR that only shows up in
one capture is more likely a decode artifact (bit slip in rtl_433, RSSI
edge condition, etc.).
"""
import sys, os, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from parse_frames import parse

hits_files = sys.argv[1:] or [
    "captures/organic-macarons-long/hits.json",
    "captures/organic-macarons-palm/hits.json",
    "captures/awesome-you-long/hits.json",
    "captures/awesome-you-touch/hits.json",
    "captures/awesome-you-decoder-test/hits.json",
    "captures/safe-song-long/hits.json",
    "captures/safe-song-flipped/hits.json",
]

# srcaddr -> {capture_dir -> count}
seen = defaultdict(lambda: defaultdict(int))

for path in hits_files:
    if not os.path.exists(path): continue
    cap = os.path.basename(os.path.dirname(path))
    for line in open(path):
        try: r = json.loads(line)
        except json.JSONDecodeError: continue
        rows = r.get("rows", [])
        if not rows: continue
        data = rows[0].get("data", "")
        if data.startswith("d391"): data = data[4:]
        if len(data) % 2: data = data[:-1]
        raw = bytes.fromhex(data)
        p = parse(raw)
        if "error" in p: continue
        seen[p["srcaddr"]][cap] += 1

# Sort by total-across-captures desc
totals = [(sum(caps.values()), addr, caps) for addr, caps in seen.items()]
totals.sort(reverse=True)

print(f"{'SRCADDR':<12} {'total':>5} {'sessions':>8}  session breakdown")
print("-" * 90)
for tot, addr, caps in totals:
    n_sessions = len(caps)
    breakdown = "  ".join(f"{c}={n}" for c, n in caps.items())
    marker = ""
    if n_sessions == 1 and tot == 1:
        marker = "  <-- one-shot, likely artifact"
    elif n_sessions >= 2:
        marker = "  <-- recurs across sessions"
    print(f"{addr:<12} {tot:>5} {n_sessions:>8}  {breakdown}{marker}")
