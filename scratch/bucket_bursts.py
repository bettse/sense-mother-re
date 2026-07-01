#!/usr/bin/env python3
"""Parse a rtl_433 stdout capture and bucket detected bursts into time windows
defined in a timeline.txt file (lines like "YYYY-MM-DD HH:MM:SS UTC  label").

Usage:  bucket_bursts.py <run-dir>
where <run-dir> contains rtl433.stdout and timeline.txt.

Reports burst counts/rates per window, split by FSK vs OOK, and optionally
re-bucketed under a fixed-gain run by RSSI threshold. RSSI is only meaningful
when rtl_433 was started with explicit gain (-g N) — with AGC, every burst
clips at ~0 dB and the threshold report is uninformative.
"""
import re, sys, os
from datetime import datetime, timezone
from collections import defaultdict

def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

def load_windows(path):
    """timeline.txt: 'YYYY-MM-DD HH:MM:SS UTC  label' per line"""
    points = []
    for line in open(path):
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+UTC\s+(\S+)", line)
        if m:
            points.append((parse_ts(m.group(1)), m.group(2)))
    points.sort()
    # consecutive pairs become windows
    return [(points[i][1], points[i][0], points[i+1][0]) for i in range(len(points)-1)]

def parse_stdout(path):
    lines = open(path).read().splitlines()
    events = []
    i = 0
    while i < len(lines):
        m = re.match(r"Detected (FSK|OOK) package\t(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", lines[i])
        if m:
            kind = m.group(1); ts = parse_ts(m.group(2))
            rssi = snr = noise = None; fn = None
            j = i + 1
            while j < len(lines) and j < i + 400 and not lines[j].startswith("Detected "):
                mr = re.search(r"RSSI:\s+(-?[\d.]+)\s+dB\s+SNR:\s+(-?[\d.]+)\s+dB\s+Noise:\s+(-?[\d.]+)\s+dB", lines[j])
                if mr:
                    rssi = float(mr.group(1)); snr = float(mr.group(2)); noise = float(mr.group(3))
                mf = re.search(r"\*\*\* Saving signal to file (g\d+_\S+\.cu8)", lines[j])
                if mf:
                    fn = mf.group(1); break
                j += 1
            if fn:
                events.append({"ts": ts, "kind": kind, "rssi": rssi, "snr": snr, "noise": noise, "fn": fn})
            i = j
        else:
            i += 1
    return events

def report(events, windows, rssi_threshold=None):
    label = "ALL" if rssi_threshold is None else f"RSSI > {rssi_threshold} dB"
    print(f"\n=== {label} ===")
    for name, a, b in windows:
        bursts = [e for e in events if a <= e["ts"] < b
                  and (rssi_threshold is None or (e["rssi"] is not None and e["rssi"] > rssi_threshold))]
        fsk = sum(1 for e in bursts if e["kind"] == "FSK")
        ook = sum(1 for e in bursts if e["kind"] == "OOK")
        dur = (b - a).total_seconds()
        rate = len(bursts) / dur if dur > 0 else 0
        print(f"  {name:20s} ({int(dur):>4d}s): {len(bursts):3d}  FSK={fsk:2d} OOK={ook:2d}  rate={rate:.2f}/s")

def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    events = parse_stdout(os.path.join(run_dir, "rtl433.stdout"))
    windows = load_windows(os.path.join(run_dir, "timeline.txt"))
    print(f"Parsed {len(events)} detection→file events  across {len(windows)} windows")
    for thr in (None, -10, -5, -3):
        report(events, windows, thr)

    # surface candidate cookie files: bursts that fall in any window with 'shake' or 'SHAKE' in name
    print("\nShake-window candidates (any RSSI):")
    for name, a, b in windows:
        if "shake" in name.lower():
            for e in events:
                if a <= e["ts"] < b:
                    rs = f"{e['rssi']:.1f}" if e['rssi'] is not None else "?"
                    print(f"  {e['fn']:30s} {e['ts'].strftime('%H:%M:%S')} {e['kind']} rssi={rs}")

if __name__ == "__main__":
    main()
