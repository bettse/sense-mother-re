#!/usr/bin/env python3
"""Parse rtl_433 Cookie captures through CC1101 PN9 de-whitening and
SimpliciTI framing.

For each frame in hits.json:
  1. Strip the 'd391' sync prefix
  2. De-whiten with CC1101 PN9 (seed 0x1FF)
  3. Extract SimpliciTI fields: LENGTH | DSTADDR(4) | SRCADDR(4) | PORT
     | DEVICE INFO | payload
  4. Decode PORT and DEVICE INFO bit-fields per SimpliciTI Spec Tables 2 & 3
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from cc1101_dewhiten import dewhiten


def decode_port(b):
    fwd = (b >> 7) & 1
    enc = (b >> 6) & 1
    port = b & 0x3F
    return fwd, enc, port


def decode_devinfo(b):
    ack_req  = (b >> 7) & 1
    sleep    = (b >> 6) & 1
    sender   = (b >> 4) & 0x3
    ack_rep  = (b >> 3) & 1
    hopcount = b & 0x7
    sender_txt = ["End Device", "Range Ext", "Access Pt", "reserved"][sender]
    return f"ack_req={ack_req} sleep={sleep} sender={sender_txt} ack_rep={ack_rep} hop={hopcount}"


def parse(raw):
    """raw = bytes AFTER the sync word."""
    clean = dewhiten(raw)
    if len(clean) < 12:
        return {"error": "too short", "clean": clean.hex()}
    length = clean[0]
    dstaddr = clean[1:5]
    srcaddr = clean[5:9]
    port_b = clean[9]
    devi_b = clean[10]
    payload = clean[11:]
    fwd, enc, port = decode_port(port_b)
    return {
        "length": length,
        "dstaddr": dstaddr.hex(),
        "srcaddr": srcaddr.hex(),
        "port_byte": port_b,
        "fwd": fwd, "encrypted": enc, "port": port,
        "devinfo_byte": devi_b,
        "devinfo": decode_devinfo(devi_b),
        "payload": payload.hex(),
        "clean": clean.hex(),
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    for arg in sys.argv[1:]:
        print(f"\n=== {arg} ===")
        seen_srcaddrs = {}
        for line in open(arg):
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
            raw = bytes.fromhex(data)
            p = parse(raw)
            if "error" in p:
                print(f"  {r.get('time','?')} SHORT ({p['error']}): {p['clean']}")
                continue
            tag = "ENC" if p['encrypted'] else "PT"
            print(f"  {r.get('time','?')} len={p['length']:2d} dst={p['dstaddr']} "
                  f"src={p['srcaddr']} port={p['port']:2d}({tag}) fwd={p['fwd']} "
                  f"payload={p['payload']}")
            seen_srcaddrs.setdefault(p['srcaddr'], 0)
            seen_srcaddrs[p['srcaddr']] += 1
        print(f"\n  distinct SRCADDRs: {seen_srcaddrs}")


if __name__ == "__main__":
    main()
