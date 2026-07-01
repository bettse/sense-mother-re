# SimpliciTI reference material

Vendored copies of Texas Instruments' SimpliciTI stack (source) and
SmartRF Packet Sniffer (Windows tool that natively dissects SimpliciTI
frames). Included in this repo because TI has deprecated SimpliciTI and
their download endpoints now require an authenticated my.ti.com session
that gates the source archives behind an export-approval flow.

The sen.se Cookie's boot log identifies its RF stack as SimpliciTI
(`teardown/mother/boot-log-fw398.txt` — `#Starting SimpliciTI...`). The
frame layout we reverse-engineered from over-the-air captures maps to
SimpliciTI's documented header format; this directory is the reference
we cross-check against.

## Contents

### Original TI archives (authoritative provenance)

Downloaded directly from TI. These are Windows self-extracting
installers wrapped in a normal zip; they need Windows / Wine to
extract, so for on-disk browsing we also keep the GitHub-mirror
extractions below.

- **`swrc099e-SimpliciTI-IAR-1.2.0-original.zip`** (12 M) — TI's
  final 1.2.0 release (SWRC099, Nov 2011)
- **`swrc132a-SimpliciTI-CCS-1.1.1-original.zip`** (9.7 M) — TI's
  1.1.1 release (SWRC132, Dec 2009)
- **`smartrf-sniffer-2.18.1.zip`** (22 M) — SmartRF Packet Sniffer
  (SWRC045, Jun 2014) — Windows GUI tool that dissects SimpliciTI
  natively with a CC1111 dongle or CC1101EM eval board
- **`SmartRF_Packet_Sniffer_2.18.1_Readme.txt`** — sniffer release
  notes for quick scanning

### Extracted source trees (readable on-disk)

Third-party GitHub mirrors of the same TI 1.1.1 and 1.2.0 releases
above, unpacked. Use these to `grep` / `less` the actual C source.

- **`simpliciti-1.2.0-mspgcc/`** — SimpliciTI 1.2.0 (primary reference).
  Mirror: <https://github.com/kubaraczkowski/SimpliciTI-mspgcc-1.2.0>
  TI's `Components/`, `Applications/`, `Projects/`, `Documents/` trees
  intact and unmodified. Notable files for our target:
  - `Components/mrfi/radios/family1/mrfi_radio.c` — CC1101 MRFI driver
  - `Components/nwk/nwk_*.[ch]` — network-layer packet format
  - `Documents/SimpliciTI Specification.pdf` — the frame-format bible
  - `Documents/Application Note on SimpliciTI Security.pdf` —
    encryption algorithm + default key
- **`simpliciti-1.1.1-ccs/`** — SimpliciTI 1.1.1 (secondary reference,
  in case sen.se firmware was built pre-1.2.0).
  Mirror: <https://github.com/juansmp/SimpliciTI-CCS-1.1.1>


## Licensing

All source and binary content in this directory is © Texas Instruments,
Inc. and redistributed unmodified from TI's official downloads. The
mirror repositories above (kubaraczkowski and juansmp on GitHub) do not
add a superseding license. Consult TI's original software license terms
before redistributing.

## Hardware needed to actually use these

- To **run the sniffer**: CC1111 USB Dongle, or a SmartRF05EB/TrxEB
  eval board with a CC1101EM daughtercard. The CC1111 dongle is the
  cheaper option and enough for our use case.
- To **run SimpliciTI as an Access Point**: any CC1101 module (~$5 on
  AliExpress) wired to a host with a SimpliciTI port. The
  `simpliciti-1.2.0-mspgcc/` build targets MSP430 Launchpad; a Pi +
  CC1101 or ESP32 + CC1101 port is more useful for HA integration,
  but requires porting SimpliciTI's `bsp/` layer to the new host.
