#!/usr/bin/env python3
"""FSK demodulator with preamble-anchored symbol timing.

Pipeline:
  1. Read .cu8, convert to complex baseband
  2. Find loudest burst window by smoothed instantaneous power
  3. FM-discriminate (angle of conj-product) with DC offset compensation
  4. Boxcar (matched filter) of the approximate symbol width
  5. Find all sub-sample-interpolated zero-crossings
  6. Refine symbol period from the median short-gap between crossings — the
     preamble (alternating bits) dominates the histogram of single-symbol gaps
  7. Phase-lock to the first preamble crossing; sample at predicted bit centers
  8. Try both polarities, pick the one whose start matches preamble pattern
  9. Search for the candidate sync word in the bit stream (any bit offset)
 10. Print bytes starting at sync word + 0

Usage:  decode_fsk_v2.py <file.cu8> [--syncs HEX,HEX,...] [--rate Hz] [--rate-range Hz,Hz]
"""
import sys, os, argparse
import numpy as np

DEFAULT_SAMPLE_RATE = 2_400_000
DEFAULT_TARGET_RATE = 111_000

def load_iq(path):
    raw = np.fromfile(path, dtype=np.uint8)
    if len(raw) % 2: raw = raw[:-1]
    iq = (raw[0::2].astype(np.float32) - 127.5) + 1j * (raw[1::2].astype(np.float32) - 127.5)
    return iq

def find_burst(iq, sample_rate, margin_s=0.0005):
    """Largest contiguous window where smoothed power > noise + 25% of dynamic range."""
    power = iq.real ** 2 + iq.imag ** 2
    w = max(8, int(sample_rate * 50e-6))
    csum = np.cumsum(np.insert(power, 0, 0.0))
    smooth = (csum[w:] - csum[:-w]) / w
    noise = np.median(smooth)
    peak = np.max(smooth)
    if peak < noise * 5:
        return 0, len(iq)
    threshold = noise + 0.25 * (peak - noise)
    above = smooth > threshold
    edges = np.diff(above.astype(np.int8))
    starts = np.where(edges == 1)[0] + 1
    ends = np.where(edges == -1)[0] + 1
    if above[0]: starts = np.insert(starts, 0, 0)
    if above[-1]: ends = np.append(ends, len(above))
    runs = sorted(zip(starts, ends), key=lambda r: r[1]-r[0], reverse=True)
    s, e = runs[0]
    m = int(sample_rate * margin_s)
    return max(0, s - m), min(len(iq), e + m + w)

def fm_discrim(iq):
    return np.angle(iq[1:] * np.conj(iq[:-1]))

def boxcar(x, n):
    if n < 2: return x
    return np.convolve(x, np.ones(n)/n, mode="same")

def zero_crossings_interp(x):
    """Sub-sample positions of zero crossings."""
    s = np.sign(x)
    s[s == 0] = 1
    idx = np.where(np.diff(s) != 0)[0]
    pos = []
    for i in idx:
        d = x[i+1] - x[i]
        if d == 0: continue
        frac = -x[i] / d
        if 0 <= frac <= 1:
            pos.append(i + frac)
    return np.array(pos)

def demodulate(iq, sample_rate, target_rate):
    disc_full = fm_discrim(iq)
    dc = float(np.mean(disc_full))
    disc = disc_full - dc

    sps_approx = sample_rate / target_rate
    smooth = boxcar(disc, max(2, int(round(sps_approx * 0.8))))
    crossings = zero_crossings_interp(smooth)
    if len(crossings) < 5:
        return None, None, None, None, dc

    gaps = np.diff(crossings)
    # Refine symbol period from gaps within 0.5..1.5 of approx (single-symbol gaps).
    short = gaps[(gaps > 0.5 * sps_approx) & (gaps < 1.5 * sps_approx)]
    sps = float(np.median(short)) if len(short) >= 5 else float(sps_approx)

    # Anchor phase from the first short-gap crossing pair (= confirmed preamble bit).
    anchor = None
    for i, g in enumerate(gaps):
        if 0.7 * sps < g < 1.3 * sps:
            anchor = crossings[i]
            break
    if anchor is None:
        anchor = crossings[0]

    # Symbol centers: half a symbol after the anchor, then every sps.
    last_idx = len(smooth) - 1
    centers = []
    c = anchor + 0.5 * sps
    while c <= last_idx:
        centers.append(c)
        c += sps
    # Also extend backward to capture preamble bits before the anchor
    back = []
    c = anchor - 0.5 * sps
    while c >= 0:
        back.append(c); c -= sps
    centers = list(reversed(back)) + centers

    bits = np.array([1 if smooth[int(round(c))] > 0 else 0 for c in centers], dtype=np.uint8)
    return bits, sps, anchor, smooth, dc

def pick_polarity(bits):
    """Pick the polarity whose longest alternating run looks most like a preamble."""
    def longest_alt_run(b):
        best = run = 0
        for i in range(1, len(b)):
            if b[i] != b[i-1]:
                run += 1
                best = max(best, run)
            else:
                run = 0
        return best
    a = longest_alt_run(bits)
    b = longest_alt_run(1 - bits)
    return bits if a >= b else (1 - bits)

def bits_to_bytes(bits, start_bit):
    out = []
    i = start_bit
    while i + 7 < len(bits):
        v = 0
        for j in range(8):
            v = (v << 1) | int(bits[i + j])
        out.append(v); i += 8
    return bytes(out)

def find_sync(bits, sync_hex):
    """Search for the given hex sync word at every bit offset.  Returns the first
    bit index where the sync starts, or None."""
    sync_bytes = bytes.fromhex(sync_hex)
    target = []
    for byte in sync_bytes:
        for shift in range(7, -1, -1):
            target.append((byte >> shift) & 1)
    target = np.array(target, dtype=np.uint8)
    n = len(target)
    for off in range(0, len(bits) - n + 1):
        if np.array_equal(bits[off:off+n], target):
            return off
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--rate", type=float, default=DEFAULT_TARGET_RATE)
    ap.add_argument("--samplerate", type=float, default=DEFAULT_SAMPLE_RATE)
    ap.add_argument("--syncs", default="d3c8,d391,2dd4,930b",
                    help="comma-separated hex sync candidates to search for")
    args = ap.parse_args()

    iq = load_iq(args.path)
    s, e = find_burst(iq, args.samplerate)
    seg = iq[s:e]
    bits, sps, anchor, smooth, dc = demodulate(seg, args.samplerate, args.rate)
    if bits is None:
        print(f"{os.path.basename(args.path)}: no demod"); return
    bits = pick_polarity(bits)

    refined_rate = args.samplerate / sps if sps else 0.0
    print(f"# {os.path.basename(args.path)}  burst={(e-s)/args.samplerate*1000:.2f}ms  "
          f"sps={sps:.3f}  refined_symrate={refined_rate/1000:.2f} kbps  "
          f"DC_offset={dc*args.samplerate/(2*np.pi)/1000:+.1f} kHz")

    # Try every sync candidate
    found = False
    for sync_hex in args.syncs.split(","):
        sync_hex = sync_hex.strip()
        for poly_label, b in (("normal", bits), ("inverted", 1 - bits)):
            off = find_sync(b, sync_hex)
            if off is not None:
                payload = bits_to_bytes(b, off)
                print(f"  sync 0x{sync_hex} ({poly_label}) at bit {off}: "
                      f"{payload[:32].hex()}")
                found = True
                break
        if found: break
    if not found:
        # No exact sync — print bits + raw bytes
        bitstr = "".join(str(b) for b in bits)
        print(f"  no sync found; bits[:200]: {bitstr[:200]}")
        print(f"  bytes (offset 0): {bits_to_bytes(bits, 0)[:32].hex()}")

if __name__ == "__main__":
    main()
