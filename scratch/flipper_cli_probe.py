#!/usr/bin/env python3
"""Send a Flipper CLI command over USB CDC and print the reply.

Purpose: debug whether `printf ... > /dev/cu.usbmodemflip*` actually reaches
the CLI parser or just gets dropped into the void.

Usage:
    flipper_cli_probe.py 'input send up short'
    flipper_cli_probe.py 'date'

Times out after 2 s of silence.
"""
import sys
import time
import glob
import serial

CMD = sys.argv[1] if len(sys.argv) > 1 else "date"

devs = glob.glob("/dev/cu.usbmodemflip*")
if not devs:
    print("no Flipper CDC found under /dev/cu.usbmodemflip*", file=sys.stderr)
    sys.exit(1)
dev = devs[0]

s = serial.Serial(dev, 115200, timeout=0.5)
# Consume any welcome banner
time.sleep(0.2)
s.reset_input_buffer()

print(f"--- {dev}: sending {CMD!r} ---", file=sys.stderr)
s.write((CMD + "\r\n").encode())
s.flush()

start = time.monotonic()
last_byte = start
buf = b""
while time.monotonic() - last_byte < 2.0 and time.monotonic() - start < 5.0:
    chunk = s.read(256)
    if chunk:
        buf += chunk
        last_byte = time.monotonic()

# Strip ANSI escapes so the output is readable
import re
clean = re.sub(rb"\x1b\[[0-9;]*[A-Za-z]", b"", buf).decode(errors="replace")
print(clean)
