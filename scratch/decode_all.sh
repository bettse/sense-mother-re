#!/usr/bin/env bash
# Decode every cookie-candidate file from run3 and dump bits side-by-side.
set -e
cd "$(dirname "$0")/.."

for f in captures/run3/g002 captures/run3/g014 captures/run3/g024 \
         captures/run3/g030 captures/run3/g035 captures/run3/g036; do
    echo "============================================"
    python3 scratch/decode_fsk.py "${f}"_915M_2400k.cu8
done
