#!/usr/bin/env python3
"""Scan rtl_433 captures for port-3 (SimpliciTI Join) frames per Cookie.

Answers: was the current-set Cookie ever seen broadcasting Join before?
If so, when did it stop? The Cookie stops re-broadcasting Join once it
successfully links to any Mother — so a session boundary between "many
Joins" and "zero Joins" is a smoking gun that the Cookie got associated
during that session (e.g. while the Mother was powered up for other RE
work).
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten


def summarize(hits_path):
    ports = {}
    srcs = {}
    joins = []
    total = 0
    for line in open(hits_path):
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
        if len(data) < 22 or len(data) % 2:
            continue
        raw = bytes.fromhex(data)
        clean = dewhiten(raw)
        if len(clean) < 12:
            continue
        length = clean[0]
        if length < 10 or length + 1 > len(clean):
            continue
        src = clean[5:9].hex()
        port = clean[9] & 0x3F
        total += 1
        ports[port] = ports.get(port, 0) + 1
        srcs.setdefault(src, {"total": 0, "ports": {}})
        srcs[src]["total"] += 1
        srcs[src]["ports"][port] = srcs[src]["ports"].get(port, 0) + 1
        if port == 3:
            joins.append((j.get("time", "?"), src, clean.hex()))
    return total, ports, srcs, joins


def main():
    base = os.path.join(os.path.dirname(__file__), "..", "captures")
    for d in sorted(glob.glob(os.path.join(base, "*/"))):
        hits = os.path.join(d, "hits.json")
        if not os.path.exists(hits):
            continue
        n, ports, srcs, joins = summarize(hits)
        print(f"\n=== {os.path.basename(d.rstrip('/'))}  ({n} frames) ===")
        print(f"  ports: {dict(sorted(ports.items()))}")
        for src, info in sorted(srcs.items(), key=lambda x: -x[1]["total"]):
            ports_str = ",".join(f"p{p}:{c}" for p, c in sorted(info["ports"].items()))
            print(f"  src {src}  {info['total']} frames  [{ports_str}]")
        if joins:
            print(f"  *** {len(joins)} JOIN frames on port 3:")
            for t, src, hexbytes in joins[:5]:
                print(f"    {t}  src={src}  {hexbytes}")


if __name__ == "__main__":
    main()
