#!/usr/bin/env python3
"""Ask Flipper's stock `subghz tx` CLI to emit a burst on 915 MHz while
rtl_sdr records raw IQ. If the SDR sees the stock burst but not our
sense_ap tx, the problem is in our FAP's TX path. If it sees neither,
the problem is downstream (antenna, distance, SDR gain, region gate).
"""
import glob
import os
import subprocess
import sys
import time

import numpy as np
import serial

CENTER = 915_000_000
SAMP_RATE = 2_400_000
DUR_SEC = 6
IQ_PATH = "/tmp/rtl_raw_stock.iq"

devs = glob.glob("/dev/cu.usbmodemflip*")
if not devs:
    print("no Flipper CDC found", file=sys.stderr)
    sys.exit(1)


def rf_scan(iq_path):
    raw = np.fromfile(iq_path, dtype=np.uint8)
    iq = (raw[0::2].astype(np.float32) - 127.5) + 1j * (raw[1::2].astype(np.float32) - 127.5)
    win = int(SAMP_RATE * 0.01)  # 10 ms
    n = len(iq) // win
    mags = np.array([10 * np.log10(np.mean(np.abs(iq[i * win : (i + 1) * win]) ** 2) + 1e-9) for i in range(n)])
    med = float(np.median(mags))
    peak = float(np.max(mags))
    p99 = float(np.percentile(mags, 99))
    above10 = int(np.sum(mags > med + 10))
    above20 = int(np.sum(mags > med + 20))
    return med, peak, p99, above10, above20, n


def do_run(label, cli_cmd):
    print(f"\n=== {label} ===")
    print(f"  cli: {cli_cmd!r}")
    n_bytes = SAMP_RATE * 2 * DUR_SEC
    rtl = subprocess.Popen(
        ["rtl_sdr", "-f", str(CENTER), "-s", str(SAMP_RATE), "-n", str(n_bytes), IQ_PATH],
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)  # let rtl_sdr get going
    s = serial.Serial(devs[0], 115200, timeout=0.3)
    time.sleep(0.2)
    s.reset_input_buffer()
    s.write((cli_cmd + "\r\n").encode())
    s.flush()
    time.sleep(4)  # let TX finish
    s.close()
    rtl.wait()
    med, peak, p99, a10, a20, n = rf_scan(IQ_PATH)
    print(f"  median: {med:.1f} dB  peak: {peak:.1f} dB  p99: {p99:.1f} dB")
    print(f"  peak-med: {peak - med:.1f} dB   > med+10: {a10}/{n}   > med+20: {a20}/{n}")


# Stock Flipper subghz tx — Princeton-style OOK on 915 MHz, 20 repeats
do_run("stock subghz tx (OOK 650 kHz)", "subghz tx 0xFFFFFF 915000000 400 20 0")

# Our custom command
do_run("our sense_ap tx (packet-mode GFSK)", "sense_ap tx")

os.path.exists(IQ_PATH) and os.unlink(IQ_PATH)
