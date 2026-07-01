#!/usr/bin/env python3
"""Quick FSK demodulator for rtl_433 .cu8 files captured from the sen.se Cookie.

Cu8 format: unsigned 8-bit IQ pairs. Output of `rtl_433 -S unknown` at the
rate it was tuned at (here: 2.4 MS/s, 915.000 MHz center).

Process:
  1. Read & convert to complex baseband.
  2. Find the burst window by instantaneous-power threshold.
  3. FM-discriminate (angle of conj-product) — positive freq → 1, negative → 0.
  4. Decimate to 1 sample per symbol at the configured symbol rate.
  5. Print bit string + any obvious preamble/sync match.

Usage:  decode_fsk.py <file.cu8> [--rate 111000] [--sps] [--center N]
"""
import sys, os, argparse
import numpy as np

def load_iq(path):
    raw = np.fromfile(path, dtype=np.uint8)
    if len(raw) % 2: raw = raw[:-1]
    iq = (raw[0::2].astype(np.float32) - 127.5) + 1j * (raw[1::2].astype(np.float32) - 127.5)
    return iq

def find_burst(iq, sample_rate, margin=0.001):
    """Return (start, end) indices of the loudest contiguous burst."""
    power = (iq.real ** 2 + iq.imag ** 2)
    # smooth with a ~50us window
    w = max(8, int(sample_rate * 50e-6))
    csum = np.cumsum(np.insert(power, 0, 0.0))
    smooth = (csum[w:] - csum[:-w]) / w
    # threshold: 3x noise floor (median of the smoothed power)
    noise = np.median(smooth)
    peak = np.max(smooth)
    if peak < noise * 5:
        return 0, len(iq)  # no clear burst — return whole file
    threshold = noise + 0.25 * (peak - noise)
    above = smooth > threshold
    if not np.any(above):
        return 0, len(iq)
    # widest contiguous run
    edges = np.diff(above.astype(np.int8))
    starts = np.where(edges == 1)[0] + 1
    ends = np.where(edges == -1)[0] + 1
    if above[0]: starts = np.insert(starts, 0, 0)
    if above[-1]: ends = np.append(ends, len(above))
    runs = list(zip(starts, ends))
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    s, e = runs[0]
    # add margin
    m = int(sample_rate * margin)
    return max(0, s - m), min(len(iq), e + m + w)

def fm_discrim(iq):
    """Instantaneous frequency in radians/sample (FM/FSK demod)."""
    return np.angle(iq[1:] * np.conj(iq[:-1]))

def estimate_dc(disc):
    """Mean instantaneous frequency — removes any residual carrier offset
    so we threshold at zero instead of at the tuner offset."""
    return float(np.mean(disc))

def symbols_from_disc(disc, sample_rate, symbol_rate):
    """Average the instantaneous frequency across each symbol period."""
    sps = sample_rate / symbol_rate
    n = int(len(disc) / sps)
    s = np.empty(n, dtype=np.float32)
    for i in range(n):
        a = int(i * sps); b = int((i+1) * sps)
        s[i] = np.mean(disc[a:b])
    return s, sps

def bits_to_hex(bits):
    """MSB-first packing."""
    out = []
    for i in range(0, len(bits) - 7, 8):
        b = 0
        for j in range(8):
            b = (b << 1) | int(bits[i + j])
        out.append(b)
    return bytes(out)

def find_preamble(bits):
    """Look for runs of >=16 alternating bits (0xAA / 0x55) and return start indices."""
    s = ''.join(str(b) for b in bits)
    candidates = []
    for pat in ("01010101010101010101", "10101010101010101010"):
        i = s.find(pat)
        if i >= 0: candidates.append((i, pat))
    return candidates

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--rate", type=float, default=111000, help="symbol rate (Hz)")
    ap.add_argument("--samplerate", type=float, default=2_400_000)
    ap.add_argument("--full", action="store_true", help="don't search for burst, demod entire file")
    args = ap.parse_args()

    iq = load_iq(args.path)
    print(f"# {os.path.basename(args.path)}  ({len(iq)} samples at {args.samplerate/1e6} MS/s = {len(iq)/args.samplerate*1000:.1f} ms)")

    if args.full:
        s, e = 0, len(iq)
    else:
        s, e = find_burst(iq, args.samplerate)
        print(f"# burst: samples [{s}:{e}]  ({(e-s)/args.samplerate*1000:.2f} ms)")

    seg = iq[s:e]
    disc = fm_discrim(seg)
    dc = estimate_dc(disc)
    print(f"# frequency-discriminator DC offset: {dc:+.4f} rad/sample (≈ {dc * args.samplerate / (2*np.pi)/1000:.1f} kHz off center)")
    disc -= dc

    syms, sps = symbols_from_disc(disc, args.samplerate, args.rate)
    bits = (syms > 0).astype(np.uint8)
    print(f"# {len(bits)} symbols at {args.rate/1e3:.1f} kbps (sps={sps:.2f})")
    bitstr = ''.join(str(b) for b in bits)
    print(f"bits:  {bitstr}")
    print(f"hex (MSB-first): {bits_to_hex(bits).hex()}")

    # try alt polarity
    bits_inv = 1 - bits
    print(f"hex (inverted):  {bits_to_hex(bits_inv).hex()}")

    pre = find_preamble(bits)
    if pre:
        for idx, pat in pre:
            print(f"# preamble {pat} found at bit index {idx} (byte ~{idx//8})")
    pre = find_preamble(bits_inv)
    if pre:
        for idx, pat in pre:
            print(f"# preamble (inverted) {pat} found at bit index {idx} (byte ~{idx//8})")

if __name__ == "__main__":
    main()
