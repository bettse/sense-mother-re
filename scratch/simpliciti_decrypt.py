#!/usr/bin/env python3
"""Attempt to decrypt sen.se Cookie beacon frames using TI's SimpliciTI
default security parameters.

Reference: `simpliciti/simpliciti-1.2.0-mspgcc/Components/simpliciti/
nwk_applications/nwk_security.c` in this repo.

Defaults straight out of that file:

    sIV  = 0x87654321
    sKey = "SimpliciTI's Key"   (16 bytes, converted with ntohl at init)
    sMAC = 0xA5

The cipher block is XTEA(key, iv || counter) → 64-bit keystream XORed with
the plaintext. For network-application frames the counter is
`00 00 00 <CTR_HINT_BYTE>` where the hint byte is sent in the clear as the
first security byte in the frame.

Encrypted plaintext layout (per Section 3.4 / Figure 4 of the
Application Note on SimpliciTI Security):

    CTR_HINT | FCS | 0xA5 (fixed MAC) | app payload

Only CTR_HINT is in the clear. FCS + MAC + payload are encrypted.

Usage:
    simpliciti_decrypt.py <hex frame after sync> [--key STR]
    simpliciti_decrypt.py --json <rtl_433 hits.json>
"""
import sys, struct, json, argparse

DEFAULT_KEY = b"SimpliciTI's Key"
DEFAULT_IV  = 0x87654321
DEFAULT_MAC = 0xA5
NUM_ROUNDS  = 32
DELTA       = 0x9E3779B9


def xtea_encipher_block(v0, v1, key_words):
    """XTEA encipher — the exact loop from nwk_security.c line 297-312."""
    s = 0
    for _ in range(NUM_ROUNDS):
        v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key_words[s & 3]))) & 0xFFFFFFFF
        s  = (s + DELTA) & 0xFFFFFFFF
        v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key_words[(s >> 11) & 3]))) & 0xFFFFFFFF
    return v0, v1


def key_to_words(key_bytes: bytes):
    """Match nwk_securityInit(): treat 16-byte key as 4 uint32 in native
    order, then ntohl-swap them. On a little-endian host this yields four
    big-endian-read uint32s from the raw ASCII."""
    assert len(key_bytes) == 16
    words = list(struct.unpack("<4I", key_bytes))
    return [struct.unpack(">I", struct.pack("<I", w))[0] for w in words]


def keystream(iv, counter, key_words, n_bytes):
    """Generate `n_bytes` of XTEA-CTR keystream starting at the given counter."""
    out = bytearray()
    while len(out) < n_bytes:
        v0, v1 = xtea_encipher_block(iv, counter, key_words)
        block = struct.pack("<II", v0, v1)     # little-endian per Section 3.5
        out.extend(block)
        counter = (counter + 1) & 0xFFFFFFFF
    return bytes(out[:n_bytes])


def try_decrypt(frame_bytes: bytes, key: bytes = DEFAULT_KEY,
                iv: int = DEFAULT_IV, mac_fixed: int = DEFAULT_MAC,
                ctr_hint_offset: int = 11) -> "dict|None":
    """Attempt to decrypt one Cookie frame. Returns dict with plaintext /
    verdict on success, None on obvious mismatch."""
    if len(frame_bytes) < ctr_hint_offset + 3:
        return None
    key_words = key_to_words(key)

    # extract fields
    ctr_hint = frame_bytes[ctr_hint_offset]
    encrypted = frame_bytes[ctr_hint_offset + 1:]   # FCS + MAC + payload (all encrypted)

    counter = ctr_hint & 0xFF                       # network app: upper 3 bytes = 0
    ks = keystream(iv, counter, key_words, len(encrypted))
    plaintext = bytes(a ^ b for a, b in zip(encrypted, ks))

    if len(plaintext) < 2:
        return None
    fcs = plaintext[0]
    mac = plaintext[1]
    payload = plaintext[2:]

    # verify: FCS should be XOR of [MAC || payload]  (calcFCS line 388-399)
    fcs_check = 0
    for b in bytes([mac]) + payload:
        fcs_check ^= b
    fcs_ok = (fcs == fcs_check)
    mac_ok = (mac == mac_fixed)

    return {
        "ctr_hint": ctr_hint,
        "fcs_byte": fcs,
        "mac_byte": mac,
        "payload": payload.hex(),
        "mac_ok":  mac_ok,
        "fcs_ok":  fcs_ok,
        "verdict": "DECRYPTED" if (mac_ok and fcs_ok) else
                   ("MAC-only-ok" if mac_ok else
                    ("FCS-only-ok" if fcs_ok else "no match")),
    }


def try_all_ctr_offsets(frame_bytes: bytes, key: bytes = DEFAULT_KEY,
                        iv: int = DEFAULT_IV) -> None:
    """We aren't 100% sure which byte in the observed frame is the CTR hint.
    Try each reasonable offset and print the outcome for each."""
    print(f"frame ({len(frame_bytes)} bytes): {frame_bytes.hex()}")
    for off in range(4, len(frame_bytes) - 2):
        r = try_decrypt(frame_bytes, key=key, iv=iv, ctr_hint_offset=off)
        if r is None:
            continue
        flag = ""
        if r["verdict"] == "DECRYPTED":
            flag = " <-- KEY MATCHES!"
        elif r["mac_ok"] or r["fcs_ok"]:
            flag = f" ({r['verdict']})"
        print(f"  ctr@{off:>2} hint={r['ctr_hint']:02x}  fcs={r['fcs_byte']:02x} mac={r['mac_byte']:02x} "
              f"payload={r['payload']}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="*", help="hex string(s) of frame data after sync (post-d391)")
    ap.add_argument("--json", help="rtl_433 hits.json to process")
    ap.add_argument("--key", default=DEFAULT_KEY.decode("latin-1"),
                    help="128-bit key as 16-char string (default: TI's 'SimpliciTI's Key')")
    ap.add_argument("--iv", default=None, help="IV in hex (default 0x87654321)")
    ap.add_argument("--all-offsets", action="store_true",
                    help="try every plausible CTR-hint offset within the frame")
    args = ap.parse_args()

    key = args.key.encode("latin-1")
    if len(key) != 16:
        sys.exit(f"key must be exactly 16 bytes; got {len(key)}")
    iv = DEFAULT_IV if args.iv is None else int(args.iv, 16)

    frames = []
    for hx in args.frames:
        raw = bytes.fromhex(hx.replace(" ", ""))
        frames.append(raw)
    if args.json:
        for line in open(args.json):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows = r.get("rows", [])
            if not rows: continue
            data = rows[0].get("data", "")
            if data.startswith("d391"):
                data = data[4:]
            if len(data) % 2: data = data[:-1]
            frames.append(bytes.fromhex(data))

    if not frames:
        ap.print_help()
        sys.exit(0)

    print(f"# Key: {key.hex()} (\"{args.key}\")")
    print(f"# IV:  0x{iv:08x}")
    print(f"# MAC fixed byte: 0x{DEFAULT_MAC:02x}\n")

    for fr in frames:
        if args.all_offsets:
            try_all_ctr_offsets(fr, key=key, iv=iv)
            print()
        else:
            r = try_decrypt(fr, key=key, iv=iv)
            if r is None:
                print(f"{fr.hex()}: frame too short"); continue
            print(f"{fr.hex()}: ctr_hint={r['ctr_hint']:02x} fcs={r['fcs_byte']:02x} "
                  f"mac={r['mac_byte']:02x} payload={r['payload']}  [{r['verdict']}]")


if __name__ == "__main__":
    main()
