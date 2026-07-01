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

- **`simpliciti-1.2.0-mspgcc/`** — SimpliciTI 1.2.0 sources. This is
  the *primary* reference. Original TI release (`swrc132`, Nov 2011)
  wrapped with an mspgcc build harness. TI's `Components/`,
  `Applications/`, `Projects/`, `Documents/` trees are intact and
  unmodified. Contains the CC1101 MRFI radio driver
  (`Components/mrfi/radios/family1/mrfi_radio.c`), the full network
  layer (`Components/nwk/*`), and 9 TI PDFs including the
  SimpliciTI Developers Notes and Specification.

  Mirror: <https://github.com/kubaraczkowski/SimpliciTI-mspgcc-1.2.0>

- **`simpliciti-1.1.1-ccs/`** — SimpliciTI 1.1.1 sources (`swrc099`,
  Dec 2009). Secondary reference kept for baseline comparison — the
  sen.se firmware could conceivably be built against 1.1.1 or 1.2.0.
  Smaller radio-family coverage than 1.2.0 but still includes CC1101
  (`family1`) and the full SimpliciTI network layer + docs.

  Mirror: <https://github.com/juansmp/SimpliciTI-CCS-1.1.1>

- **`smartrf-sniffer-2.18.1.zip`** — TI SmartRF Packet Sniffer 2.18.1
  (Jun 2014, `swrc045z`). Windows-only GUI tool that captures 915 MHz
  traffic via a CC1111 USB Dongle (or CC1101EM + SmartRF eval board)
  and produces field-dissected packet views in Wireshark format.
  **Supports SimpliciTI versions 1.0.0 / 1.0.4 / 1.0.6 / 1.1.0 /
  1.1.1 / 1.2.0.** Zip contains both `Setup_SmartRF_Packet_Sniffer_
  2.18.0.exe` and the 2.18.1 setup EXE.

  Original download: <https://www.ti.com/tool/PACKET-SNIFFER>
  (still un-authenticated as of June 2026;
  `https://dr-download.ti.com/software-development/support-software/MD-WL2rMfHrNh/01.00.00.0Z/swrc045z.zip`).
  Vendored anyway to survive future URL changes.

- **`SmartRF_Packet_Sniffer_2.18.1_Readme.txt`** — extracted release
  notes, quick-scan version history.

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
