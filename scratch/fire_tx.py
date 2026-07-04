#!/usr/bin/env python3
"""Fire N `sense_ap tx` bursts to the Flipper CLI over CDC.

Bare `printf 'sense_ap tx\\r\\n' > /dev/cu.usbmodemflip*` in a shell loop
does not reliably reach the CLI parser — each open/write/close cycle
seems to lose bytes at the tty layer on macOS. This uses pyserial with
a single persistent connection so every command lands.

Usage: fire_tx.py [count=3] [gap_seconds=2.0]
"""
import sys
import time
import glob
import serial

count = int(sys.argv[1]) if len(sys.argv) > 1 else 3
gap = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

devs = glob.glob("/dev/cu.usbmodemflip*")
if not devs:
    print("no Flipper CDC found", file=sys.stderr)
    sys.exit(1)

s = serial.Serial(devs[0], 115200, timeout=0.3)
time.sleep(0.2)
s.reset_input_buffer()

for i in range(count):
    s.write(b"sense_ap tx\r\n")
    s.flush()
    print(f"[{i + 1}/{count}] sent sense_ap tx", file=sys.stderr)
    if i < count - 1:
        time.sleep(gap)

# Drain response briefly so the CLI prompt returns cleanly
time.sleep(0.5)
s.read(4096)
