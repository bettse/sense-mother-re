#!/usr/bin/env python3
"""Look for a beacon-style cadence among FSK bursts in a rtl_433 run.

For each FSK burst it parses: timestamp, RSSI, SNR, noise, file path, and the
detected pulse-period histograms emitted by rtl_433 in analyzer (-A) mode.
Then it groups bursts by pulse-period fingerprint, hoping the Cookie's frames
all share the same characteristic period."""
import re, sys, os
from datetime import datetime, timezone

def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

def parse_stdout(path):
    lines = open(path).read().splitlines()
    events = []
    i = 0
    while i < len(lines):
        m = re.match(r"Detected (FSK|OOK) package\t(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", lines[i])
        if m:
            kind = m.group(1); ts = parse_ts(m.group(2))
            rec = {"ts": ts, "kind": kind, "rssi": None, "snr": None, "noise": None, "fn": None,
                   "total_count": None, "total_us": None, "freq_off": None,
                   "pulse_widths": [], "gap_widths": []}
            state = None
            j = i + 1
            while j < len(lines) and j < i + 400 and not lines[j].startswith("Detected "):
                line = lines[j]
                mt = re.match(r"Total count:\s+(\d+),\s+width:\s+([\d.]+) ms", line)
                if mt:
                    rec["total_count"] = int(mt.group(1)); rec["total_us"] = float(mt.group(2)) * 1000
                mp = re.match(r"Pulse width distribution:", line);
                if mp: state = "pw"
                mg = re.match(r"Gap width distribution:", line);
                if mg: state = "gap"
                mpp = re.match(r"Pulse period distribution:|Pulse timing distribution:", line);
                if mpp: state = "other"
                if state in ("pw", "gap"):
                    mb = re.match(r"\s*\[\s*\d+\] count:\s+(\d+),\s+width:\s+(\d+) us", line)
                    if mb:
                        ent = (int(mb.group(1)), int(mb.group(2)))
                        if state == "pw": rec["pulse_widths"].append(ent)
                        else: rec["gap_widths"].append(ent)
                mr = re.search(r"RSSI:\s+(-?[\d.]+)\s+dB\s+SNR:\s+(-?[\d.]+)\s+dB\s+Noise:\s+(-?[\d.]+)\s+dB", line)
                if mr:
                    rec["rssi"] = float(mr.group(1)); rec["snr"] = float(mr.group(2)); rec["noise"] = float(mr.group(3))
                mfo = re.search(r"Frequency offsets \[F1, F2\]:\s+(-?\d+),\s+(-?\d+)", line)
                if mfo:
                    rec["freq_off"] = (int(mfo.group(1)), int(mfo.group(2)))
                mf = re.search(r"\*\*\* Saving signal to file (g\d+_\S+\.cu8)", line)
                if mf:
                    rec["fn"] = mf.group(1); break
                j += 1
            events.append(rec)
            i = j
        else:
            i += 1
    return events

def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    events = parse_stdout(os.path.join(run_dir, "rtl433.stdout"))
    fsk = [e for e in events if e["kind"] == "FSK" and e["fn"] is not None]
    print(f"{len(fsk)} FSK bursts (with saved file)")
    print(f"\n{'file':30s} {'time':10s} {'rssi':>7s} {'snr':>6s} {'dur_us':>8s} {'F1':>7s} {'F2':>7s}  dominant_pw")
    for e in sorted(fsk, key=lambda r: r["ts"]):
        rssi = f"{e['rssi']:.1f}" if e['rssi'] is not None else "?"
        snr = f"{e['snr']:.1f}" if e['snr'] is not None else "?"
        dur = f"{e['total_us']:.0f}" if e['total_us'] is not None else "?"
        f1 = f"{e['freq_off'][0]}" if e['freq_off'] else "?"
        f2 = f"{e['freq_off'][1]}" if e['freq_off'] else "?"
        # dominant pulse width: largest-count entry
        if e["pulse_widths"]:
            dom = max(e["pulse_widths"], key=lambda x: x[0])
            dom_str = f"{dom[1]}us×{dom[0]}"
        else:
            dom_str = "?"
        print(f"{e['fn']:30s} {e['ts'].strftime('%H:%M:%S'):10s} {rssi:>7s} {snr:>6s} {dur:>8s} {f1:>7s} {f2:>7s}  {dom_str}")

    # inter-burst gap analysis
    times = [e["ts"] for e in sorted(fsk, key=lambda r: r["ts"])]
    if len(times) > 1:
        print("\nInter-FSK-burst gaps (seconds):")
        for a, b in zip(times, times[1:]):
            print(f"  {(b-a).total_seconds():.1f}")

if __name__ == "__main__":
    main()
