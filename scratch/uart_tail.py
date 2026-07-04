#!/usr/bin/env python3
"""Headless UART reader — pio device monitor won't run in background because
miniterm calls termios on stdin. This is a stdin-free equivalent.

Bytes are streamed to stdout AND to a stable file (default /tmp/flipper_uart.log).
Uses exclusive open so a second reader will EAGAIN instead of corrupting both
streams. Auto-reconnects on disconnect / SerialException.
"""
import sys, serial, time, os

DEV = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-834220"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 230400
LOGFILE = sys.argv[3] if len(sys.argv) > 3 else "/tmp/flipper_uart.log"

log = open(LOGFILE, "ab", buffering=0)

while True:
    try:
        with serial.Serial(DEV, BAUD, timeout=0.5, exclusive=True) as s:
            print(f"# opened {DEV} @ {BAUD}", file=sys.stderr, flush=True)
            while True:
                b = s.read(256)
                if b:
                    sys.stdout.buffer.write(b)
                    sys.stdout.buffer.flush()
                    log.write(b)
    except serial.SerialException as e:
        print(f"# {DEV}: {e} — retrying in 1s", file=sys.stderr, flush=True)
        time.sleep(1)
    except KeyboardInterrupt:
        break
