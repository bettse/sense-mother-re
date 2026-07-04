# Sense Mother AP — Flipper Zero .fap (phase 1)

RX-only prototype for reviving sen.se Mother / Cookie hardware.
Configures the Flipper's CC1101 to the sen.se SimpliciTI PHY,
receives packets, parses them, and dumps the fields to the debug log.

**Phase 1 scope:** validate that the Flipper's CC1101 can lock onto
real Cookie beacons. If we see `port=7` frames from the SRCADDRs in the
top-level README's known-Cookies table, the preset is correct and we
can move on to phase 2 (Join reply / TX).

## PHY summary

Set at `cc1101_preset.h`:

| Parameter | Value | Register |
|---|---|---|
| Band | 915 MHz (US) — change `SENSE_FREQ` for EU 868 | (runtime) |
| Modulation | 2-GFSK | MDMCFG2 = 0x13 |
| Bit rate | 99.98 kbps | MDMCFG4/3 = 0x8B / 0xF8 |
| Deviation | ~47 kHz | DEVIATN = 0x47 |
| RX BW | 203 kHz | MDMCFG4 = 0x8B |
| Sync word | 0xD391 | SYNC1/0 = 0xD3 / 0x91 |
| Whitening | PN9 ON | PKTCTRL0 = 0x41 |
| Length | Variable | PKTCTRL0 = 0x41 |
| HW CRC | Off (soft-check in future phase) | PKTCTRL0.CRC_EN = 0 |
| GDO0 | Sync-detect / EOP strobe | IOCFG0 = 0x06 |

## Build

Requires the Flipper build tool (`ufbt`):

```bash
cd flipper/sense_mother_ap
ufbt
```

Produces `dist/f7-C/sense_mother_ap.fap`. Copy to Flipper's
`/ext/apps/Sub-GHz/` via qFlipper or:

```bash
ufbt launch
```

## Run

1. Sub-GHz → Apps → Sense Mother AP.
2. Screen shows `listening…`. Attach a serial console
   (`ufbt cli` or 115200 8N1 on the USB CDC) to see `FURI_LOG_I` output.
3. Bring a Cookie into range. Expect port-7 PLL beacons every ~15 s
   and port-3 Join broadcasts every ~1 min (marked `<JOIN>` in the log).

## Expected log line

```
[I][SenseMotherAP] len=11 dst=ffffffff src=1fa82525 port=7(PT) fwd=0 sender=0 rssi=-58 payload=00f5 43
```

Cross-check `src` against the SRCADDR table in the top-level README.

## What this doesn't do yet

- **No TX.** Cookies won't link. Phase 2 = Join reply per SimpliciTI
  Spec Table 16.
- **No CRC validation.** HW CRC is disabled so we see even malformed
  frames during PHY bring-up. Turn on `PKTCTRL0.CRC_EN=1` (bit 2) once
  the preset is confirmed lock-solid.
- **No settings UI.** Frequency is compile-time. Add EU 868 toggle in
  phase 2.

## If it doesn't decode

Symptom → likely cause:

- **Frame count stays 0 next to a live Cookie** — sync word not
  detected. Try MDMCFG2 = 0x02 (sync mode = 16/16 exact match instead
  of 30/32 + CS). If still zero, check the frequency (US 915 vs EU 868).
- **Bad count climbs, RX count stays 0** — length byte is wild.
  Probably PN9 not applied. Confirm `PKTCTRL0 = 0x41`. If sen.se
  actually uses WHITE_DATA=0, flip PKTCTRL0 to 0x01 (no whitening) and
  call `pn9_dewhiten(&frame[1], len_byte)` in software before parsing.
- **Frames arrive but SRCADDR bytes are random** — bit rate off.
  Compare against RTL-SDR flex decoder capture (`captures/*.json`) and
  adjust MDMCFG4/3.

## Fallback: bit-mode debug capture

If packet-mode won't lock, temporarily change to CC1101 async serial
mode (PKTCTRL0 = 0x30, IOCFG0 = 0x0C = serial data output) and pipe
GDO0 to logic-analyzer for direct bit inspection. Restore `0x41` once
you know the sync + bitrate are correct.
