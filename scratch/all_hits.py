#!/usr/bin/env python3
"""Dump EVERY rtl_433 hit, however short/ambiguous, with dewhitening
applied. Useful when our short TX bursts might land in the JSON but
get filtered by the stricter parse_frames.py / dewhiten_hits.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten

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
    t = j.get("time", "?")
    orig = data
    if data.startswith("d391"):
        data = data[4:]
    if len(data) % 2:
        data = data[:-1]
    try:
        raw = bytes.fromhex(data)
    except ValueError:
        print(f"  {t} raw={rawlen}b {orig}  (bad hex)")
        continue
    clean = dewhiten(raw)
    marker = ""
    if b"\xca\xfe\xf0\x0d" in clean:
        marker = "  <-- CAFEF00D"
    elif b"\xde\xad\xbe\xef" in clean:
        marker = "  <-- DEADBEEF"
    elif len(clean) >= 1 and clean[0] == 0x11:
        marker = "  <-- LEN=17"
    print(f"  {t} raw={rawlen}b whitened={raw.hex()} dewhitened={clean.hex()}{marker}")
