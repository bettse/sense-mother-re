#!/usr/bin/env python3
"""Sniff raw IQ at 915 MHz during a Flipper test-TX window and check
whether ANY signal energy shows up above noise. Uses rtl_sdr to record,
numpy to compute peak power in narrow FFT bins around 915 MHz.

Purpose: sidestep rtl_433's flex decoder entirely — if our TX isn't
producing enough RF for any decoder to catch, does the SDR even see
carrier at 915 MHz when we fire?
"""
import os
import subprocess
import sys
import time
import numpy as np

RTLSDR = "rtl_sdr"
DUR_SEC = 8
SAMP_RATE = 2_400_000
CENTER = 915_000_000
IQ_PATH = "/tmp/rtl_raw.iq"

print(f"recording {DUR_SEC}s of IQ @ {CENTER/1e6} MHz, {SAMP_RATE/1e6} MS/s", file=sys.stderr)
n_bytes = SAMP_RATE * 2 * DUR_SEC  # 2 bytes per sample (I/Q)
subprocess.run(
    [RTLSDR, "-f", str(CENTER), "-s", str(SAMP_RATE), "-n", str(n_bytes), IQ_PATH],
    stderr=subprocess.DEVNULL,
    check=True,
)

# Read as uint8, convert to complex float
raw = np.fromfile(IQ_PATH, dtype=np.uint8)
iq = (raw[0::2].astype(np.float32) - 127.5) + 1j * (raw[1::2].astype(np.float32) - 127.5)
print(f"got {len(iq)} samples", file=sys.stderr)

# Compute power over 10ms windows so bursts show up
window = int(SAMP_RATE * 0.01)  # 10 ms per window
n_win = len(iq) // window
mags = np.zeros(n_win)
for i in range(n_win):
    seg = iq[i * window : (i + 1) * window]
    mags[i] = 10 * np.log10(np.mean(np.abs(seg) ** 2) + 1e-9)

median = float(np.median(mags))
peak = float(np.max(mags))
p99 = float(np.percentile(mags, 99))
print(f"noise median: {median:.1f} dB  |  p99: {p99:.1f} dB  |  peak: {peak:.1f} dB")
print(f"peak - median: {peak - median:.1f} dB   (>10 dB = clear burst)")
above10 = int(np.sum(mags > median + 10))
above20 = int(np.sum(mags > median + 20))
print(f"windows > median+10 dB: {above10}   > median+20 dB: {above20}   (of {n_win})")

os.unlink(IQ_PATH)
