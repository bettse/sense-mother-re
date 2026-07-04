#!/usr/bin/env python3
"""Read rtl_433 JSON lines from stdin, print a one-line summary per frame
with dewhitened src/dst/port/payload. Suitable for `tail -F | python3 ...`.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten

SENDER = {0: "ED", 1: "RE", 2: "AP", 3: "res"}

for line in sys.stdin:
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
        data = data[:-1]
    try:
        raw = bytes.fromhex(data)
    except ValueError:
        continue
    clean = dewhiten(raw)
    if len(clean) < 12:
        continue
    length = clean[0]
    if length < 10 or length + 1 > len(clean):
        continue
    dst = clean[1:5].hex()
    src = clean[5:9].hex()
    port_b = clean[9]
    port = port_b & 0x3F
    fwd = (port_b >> 7) & 1
    sender = (clean[10] >> 4) & 3
    payload = clean[11 : length + 1].hex()
    t = j.get("time", "?")
    bcast = "*BCAST*" if dst == "ffffffff" else dst
    print(
        f"{t}  src={src} → {bcast}  port={port:>2}  sender={SENDER[sender]}  fwd={fwd}  payload={payload}",
        flush=True,
    )
