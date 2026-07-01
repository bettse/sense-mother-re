# sen.se Mother / Cookie — Reverse Engineering Notes

Project goal: figure out whether the original sen.se Mother hub + temperature
Cookie (defunct since 2017 sen.se liquidation) can be revived enough to push
bed-surface temperature readings into Home Assistant.

Origin: Claude Code session `9d738d5b-6725-47fb-9432-fcc72f327f4b`
(`~/.claude/projects/-Users-bettse-Downloads/9d738d5b-6725-47fb-9432-fcc72f327f4b.jsonl`).

This folder collects FCC filings for the original hardware and my analysis of
what's actually inside.

## Why this folder exists

The "buy a Mother on eBay and run it" path requires either:

1. The original sen.se cloud (gone — French company went into judicial
   liquidation in 2017, `in.sen.se` is dead).
2. A drop-in cloud emulator — `ccarlo64/freemother` exists but only handles
   the sleep Cookie (Feed type 6) and pings (Feed type 1). It does **not**
   parse temperature Cookies. Project last touched January 2021, 5 stars,
   4 open issues, 0 closed. Not a complete solution.
3. Bypass the Mother entirely — sniff the Cookie's 915 MHz radio directly
   with an SDR or a CC1101-compatible receiver and decode the frames.

Path 3 is what this folder is research toward. That requires understanding
the Cookie's RF protocol, which is undocumented but legally documented just
enough in the FCC filings to bootstrap.

## Source: FCC filings (US only — 915 MHz)

| FCC ID | Product | Date | URL |
|---|---|---|---|
| 2ABGNCOO001 | Cookie (COO001) | 2014-03-31 | https://fcc.report/FCC-ID/2ABGNCOO001/ |
| 2ABGNMOM001 | Mother (MOM001) | 2014-03-31 | https://fcc.report/FCC-ID/2ABGNMOM001/ |
| 2ABGNPEA001 | ThermoPeanut (PEA001) — BLE, NOT useful | 2016-06-21 | https://fcc.report/FCC-ID/2ABGNPEA001/ |

EU-region units use 868 MHz (CE/ETSI filings, not FCC). Confirm region of any
eBay unit before tuning a receiver. Test report serial numbers / labels in the
filings here are for the 902-928 MHz ISM band US version only.

### Why ThermoPeanut isn't a shortcut

It's BLE (2.4 GHz), but sen.se put a per-device auth key on the server side.
With the cloud dead, the key handshake can't be completed. The device pairs
but no decoded payload is accessible. Documented for completeness, not as a
path forward.

## What's in this folder

```
sense-mother-re/
├── README.md                      this file
├── fetch.sh                       re-pull all FCC exhibits idempotently
├── sen-se-mom4co-us-specsheet-12.pdf   original sen.se marketing spec sheet
├── fcc/                           FCC exhibits, both devices
│   ├── cookie/
│   │   ├── internal-photos.pdf    PCB photos (low-res; chip markings illegible)
│   │   ├── external-photos.pdf
│   │   ├── rf-test-report.pdf     RF parameters — see "RF Findings" below
│   │   ├── user-manual.pdf
│   │   ├── label-info.pdf
│   │   ├── label-location.pdf
│   │   ├── test-setup.pdf
│   │   └── extracted/             raw images extracted via pdfimages
│   └── mother/
│       ├── internal-photos.pdf    PCB photos — main board + radio daughtercard
│       ├── external-photos.pdf
│       ├── rf-test-report.pdf
│       ├── user-manual.pdf
│       ├── label-info.pdf
│       ├── label-location.pdf
│       ├── test-setup.pdf
│       └── extracted/
├── teardown/                      bench teardown photos
│   └── mother/                    Mother PCBs after disassembly (2026-06-30)
├── captures/                      RF captures, one dir per session
├── scratch/                       analysis scripts
└── simpliciti/                    vendored TI SimpliciTI source + SmartRF Sniffer
```

## What the FCC photos actually show

### Cookie (COO001)

Pawn-shaped 2-layer PCB, silkscreen marked "V2.9b". Round bottom + narrower
stem. Visual estimate from the ruler in the photo: round section ~24 mm
diameter, total board height ~35 mm.

Front side carries:

- One small QFN package (radio + MCU SoC, likely combined — see below)
- A second smaller chip (probably the temperature sensor — could be a
  TMP102, SHT2x, MCP9808-class I2C sensor)
- Crystal oscillator + matching passives
- A few discrete passives near the antenna

Back side carries:

- PCB trace antenna (meander/F-style, on the round bottom area)
- Two circular contact pads for a **CR2016** coin cell (confirmed by the
  sen.se spec sheet — 4 mm total Cookie thickness rules out CR2032).

**Cannot identify the radio chip from these photos** — the FCC submission used
~700 px JPEGs and silkscreen markings are blurred. The chip class is inferable
from the RF behavior (see below) but exact part number requires physical
inspection of an actual Cookie under magnification.

### Cookies are all the same hardware

Important sourcing note: there is **only one Cookie SKU**, not separate
"temperature / sleep / drink / presence" variants. The FCC filing has a single
model number (COO001), and the user manual page 1 states it directly:

> "So many skills in just one tiny sensor. Motion Cookies are seamlessly
> reprogrammed according to what you want to use them for. You no longer need
> a specific device for each one of your needs."

What sen.se sold as "apps" was 100% cloud-side interpretation. Every Cookie
has the same accelerometer + temperature + battery payload; the Mother (and
cloud) just decided which fields to surface. Marketing called them "Motion
Cookies" — strongly implying the accelerometer was primary and temperature
rode along on every transmission for free.

Implications:

- Buy any Cookie on eBay — listings won't be (and shouldn't be) labeled by
  "type." Shop on quantity and condition.
- Decoding one Cookie's frame gives you temperature for all of them.
- Multiple Cookies = multi-zone bed sensing or redundancy. Frames should
  carry a unique device ID byte for routing.

### Mother (MOM001)

Two-board sandwich:

- Main PCB: ARM-class MCU (large QFN, mid-board), TSSOP package (probably
  flash/EEPROM or power management), large electrolytic cap, multiple
  smaller QFNs. The Mother needs WiFi/Ethernet for the in.sen.se uplink
  plus its proprietary 915 MHz downlink.
- Radio daughtercard: looks like essentially the same 915 MHz radio module
  as the Cookie, with its own PCB trace antenna. Manually scrawled "wddo1"
  silkscreen on the antenna area in the photo.

Same limitation — chip markings illegible in the FCC photos.

## RF findings (from Cookie test report ES131204018E)

| Parameter | Value | Note |
|---|---|---|
| Operating frequency | 915 MHz | Single fixed channel |
| 99% occupied BW | 362.73 kHz | |
| 20 dB BW | 388.34 kHz | |
| Channel count | 1 | Confirmed by FCC Part 15.249 cert |
| Modulation | (not stated explicitly) | Inferred 2-FSK/GFSK from spectrum shape |
| Antenna | PCB integrated, 0 dBi | |
| Power supply | 3 V (CR2032) | |
| TX duty cycle | Intermittent | Typical sensor-node behavior |

Critical inference: **Part 15.249 is the certification for non-hopping,
non-spread-spectrum low-power intentional radiators.** This rules out
frequency hopping — the Cookie transmits at 915 MHz fixed. No FHSS chase
logic needed in a receiver.

Modulation type isn't named in the test report (typical — they only test
emissions compliance, not protocol). But: 362 kHz occupied BW at 915 MHz
with a bell-shaped spectrum is a textbook 2-FSK / GFSK signature, almost
certainly **100-250 kbps**. The bandwidth aligns with TI CC1101 standard
configs at ~250 kbps GFSK.

Most probable radio chip family (cannot confirm without physical teardown):

- TI **CC1101** — standalone 915 MHz transceiver, paired with separate MCU
- TI **CC1110/CC1111** — CC1101 radio + 8051 MCU in one QFN36, very popular
  for sensor nodes in 2013-2014
- Silicon Labs **Si446x** — similar specs, less common in EU-designed nodes
- Semtech **SX12xx** — Lora-capable but also supports plain FSK

CC1110/CC1111 is the educated guess — single QFN matching what's visible,
common French/EU IoT-startup choice, supports the bandwidth shown.

## Reverse engineering plan

### Phase 1: physical confirmation (need an actual Cookie)

1. Buy a Mother + at least one Cookie on eBay (any Cookie — they're
   identical hardware; see "Cookies are all the same hardware" above).
   Multiple Cookies cheap is better than one expensive one. The Mother
   itself isn't strictly required for sniffing, but useful for confirming
   the Cookie is alive and TXing.
2. Inspect Cookie PCB under a USB microscope. Read radio chip markings.
3. Confirm region (FCC US 915 MHz vs CE EU 868 MHz). Match SDR tuning.
4. Battery type: **CR2016** (confirmed by sen.se spec sheet).

### Phase 2: capture

Sniff the Cookie's transmissions while it's powered on. Two viable rigs:

- **RTL-SDR** ($30) — cheapest. Covers 915 MHz. Limited to ~2.4 MHz
  bandwidth (more than enough for a 362 kHz signal). Use with:
  - **Universal Radio Hacker (URH)** — visual demod + framing analysis.
    Built exactly for this kind of work. https://github.com/jopohl/urh
  - **rtl_433** — already has decoders for ~200 different 433/868/915 MHz
    sensor protocols; worth trying first in case sen.se used a stock
    protocol on top of CC1101. https://github.com/merbanan/rtl_433
- **HackRF One** ($300) — broader bandwidth, TX-capable if you ever want
  to simulate a Cookie. Probably overkill for this.

URH workflow:

1. Tune to 915 MHz, sample rate 2 MS/s, AM/FM demod to identify the burst.
2. Switch to FSK demod, eyeball the symbol rate from zero crossings.
3. Auto-detect framing (preamble, sync word, length, payload, CRC).
4. Capture multiple Cookies / temperatures / battery levels to build a
   training set for protocol inference.

rtl_433 workflow:

1. Run with `-A` (analyze mode) to see if any existing decoder matches.
2. If unknown, use `-f 915M -s 250k -X "n=sense,m=FSK_PCM,..."` to define
   a custom decoder once symbol rate / sync word are known from URH.

### Phase 3: decode

Realistic frame structure to look for (typical sub-GHz IoT pattern):

- Preamble: 0xAAAA... (alternating bits for clock recovery)
- Sync word: 2-4 bytes (chip default if they didn't customize)
- Length byte
- Cookie unique ID (likely the same digits printed on the Cookie back)
- Sequence counter
- Payload type byte (this is what would distinguish temp/sleep/presence)
- Payload (temperature as int16, probably 0.01°C steps or similar)
- CRC16

Sen.se's protocol is almost certainly unencrypted — 2013-vintage French
startup, battery-life-constrained device, no key exchange in the photos.

**Confirmed beaconing behavior (from the spec sheet):** "Constantly signal
their presence to the closest Mother" + "Can stock up to 15 days of data
when away from Mother's range." Implication: the Cookie transmits its own
presence beacons periodically without needing a paired Mother. We don't
have to spoof an ack or get the Mother online to sniff. Shaking the Cookie
will likely increase TX rate (accelerometer event), but even idle the
device should beacon. Battery life math (CR2016 ≈ 90 mAh, 6–12 month
autonomy) implies idle beacon period in the range of minutes, not seconds
— budget several minutes per capture session.

### Phase 4: bridge to Home Assistant

Once frames decode, five viable integration paths ordered by friction:

**1. rtl_433 → MQTT → HA** (lowest friction; bench-grade)
- Tools used during decoding *are* the integration. Single deployment.
- rtl_433 publishes MQTT with HA-discovery format → sensor auto-appears
  in HA. No YAML.
- Needs a Linux host (Pi Zero 2 W is fine) and an RTL-SDR ($30).
- Requires running a Linux box you didn't already have.

**2. LilyGO T-Embed CC1101 + ESPHome** (preferred for this project)
- ESP32-S3 dev board with CC1101 covering 779-928 MHz built in, color
  display, battery, antenna. Ships blank; flash whatever you want.
  https://www.lilygo.cc/products/t-embed-cc1101
- ESPHome external_component `dbuezas/esphome-cc1101` (actively maintained
  as of mid-2026) provides:
  - Raw RX exposed as `remote_receiver` source for lambda decoders
  - RSSI sensor
  - Runtime-tunable frequency and bandwidth as HA `number` entities —
    very useful during bring-up, you can sweep from the HA UI
  - Multi-receiver per node supported
  - https://github.com/dbuezas/esphome-cc1101
- Native ESPHome API to HA. No MQTT broker required.
- No Linux box anywhere.
- **Caveat:** writing an FSK frame parser as a C++ lambda is harder than
  an rtl_433 `-X` decoder string. You handle preamble lock, sync word
  detection, bit unpacking, CRC in lambda land per pulse-edge. Plan to
  prototype the decoder in rtl_433 first (on a borrowed laptop with a
  borrowed RTL-SDR) and *port* the working logic to the lambda — then
  the T-Embed becomes the permanent receiver.

**3. OpenMQTTGateway on ESP32 + CC1101**
- Pre-built multi-protocol firmware (sub-GHz, BLE, 433 MHz, IR).
- HA discovery built-in; new protocols added by PR.
- Middle ground between rtl_433 and bespoke ESPHome.
- https://docs.openmqttgateway.com/

**4. Pi + bare CC1101 via SPI + Python**
- $3 CC1101 module wired to Pi GPIO. Cheaper than RTL-SDR.
- Libraries like `pyCC1101` exist but are minimal; framing is on you.
- Publish to MQTT.

**5. Custom HA integration (`custom_component`)**
- Python integration talking to CC1101 over network/serial/MQTT.
- High effort, low payoff unless you plan to publish for others.

The Mother itself becomes unnecessary in all five paths — the Cookies talk
directly to your receiver. The Mother only existed to NAT 915 MHz → WiFi →
sen.se cloud. Keep it as a shelf curio.

**Recommended path for this project:** decode with **#1 (rtl_433 on any
laptop + RTL-SDR)** because the toolchain is purpose-built for sub-GHz
decoder development. Then deploy with **#2 (T-Embed CC1101 + ESPHome)** for
the permanent always-on receiver next to the bed. RTL-SDR retires to a
drawer for the next project.

> **Note (post-bench-session):** the passive RX-only paths (#1 and a
> TX-disabled #2) get you the Cookie's *presence* and *device ID* but
> not its sensor readings — those aren't in the periodic beacons; they're
> held locally until Mother polls for them. To actually read bed
> temperature, the receiver has to transmit Mother's downlink request.
> That bumps the recommendation to **TX-capable hardware** — either #2
> (the T-Embed CC1101 *is* TX-capable, the radio block supports it),
> #3 (OpenMQTTGateway with a CC1101 module), or #4 (Pi + CC1101). RTL-SDR
> alone cannot fulfill the end-to-end goal. See "Experiments run" and
> "Open work to enable read-out" below for what was actually measured.

## Time / difficulty estimate

Original guess was 20–40 hours for the SDR-side decode. Actual elapsed
for the passive layer was closer to **an afternoon of bench work** —
rtl_433 turned out to handle the protocol natively once we identified
the CC1101 default-config sync word, and three Cookies were enough to
nail down the device-ID byte positions.

But that passive layer **doesn't get us bed temperature.** As documented
in "Experiments run" below, beacons only carry presence + ID; sensor
data is buffered and uploaded on Mother's request. So the project as
stated still needs another work session of comparable size to capture
a Mother↔Cookie exchange and replicate Mother's downlink with TX
hardware.

## RF capture findings (June 2026 bench session)

Captured live transmissions from a real Cookie powered by a CR2016 next to
an RTL-SDR antenna. Files in `captures/run3/` (touch-test with cookie on
antenna, RTL-SDR gain locked to 0). Analyzers in `scratch/`.

### Silicon — Cookie (confirmed by physical inspection)

The largest IC on the Cookie PCB reads:

```
CC430
F5137
TI 36K E
A32Y G4
```

That's **TI CC430F5137** — an MSP430 16-bit MCU + CC1101 sub-1 GHz radio
in one QFN package. Everything we measured over the air now has an
authoritative explanation: the radio block is literally CC1101.

### RF parameters

All defaults of the CC1101 "Standard" 100 kbps GFSK preset. The Cookie
firmware appears to have taken the SmartRF Studio defaults essentially
unchanged.

- **Modulation: 2-GFSK** (CC1101 default)
- **Symbol rate: 99.97 kbps** (CC1101's "100 kbps" preset)
- **Deviation: ~±50 kHz** (CC1101 default for this preset)
- **Center frequency: 915.000 MHz**, very stable
- **Sync word: `0xD391`**, used in 16-bit and sometimes doubled 32-bit
  form across bursts (CC1101 `MDMCFG2.SYNC_MODE` 2 vs 3) — this is the
  CC1101 chip default sync word
- **Burst duration: ~1.8–3.5 ms** → ~30 bytes including
  preamble + sync + length + payload + CRC
- **Idle beacon period: ~10–20 s** (matches the spec sheet's "constantly
  signal presence" line). Some bursts are doubled (~1 s apart).

### Decoding live with rtl_433

rtl_433 has a flexible-decoder framework that handles this protocol
cleanly with one line:

```bash
rtl_433 -f 915M -s 2400000 -g 0 \
        -X 'n=cookie,m=FSK_PCM,s=10,l=10,r=400,preamble=d391' \
        -F json:hits.json -F log:rtl433.log
```

Notes on the flags:
- `-f 915M` — US ISM band; use `868M` for EU Cookies
- `-s 2400000` — 2.4 MS/s gives ~24 samples per 10 µs symbol, plenty
- `-g 0` — minimum LNA gain; required when the Cookie is touching the
  antenna or it clips. Higher gain is fine for room-scale distances.
- `m=FSK_PCM,s=10,l=10` — 10 µs short = 10 µs long, i.e. 100 kbps NRZ
- `r=400` — 400 µs reset gap between frames
- `preamble=d391` — CC1101 default sync, used to lock byte alignment

Each decoded frame lands in `hits.json` as a "cookie" model, e.g.:

```
{"model":"cookie","data":"d391f41ee265129a943ec27dd259764e", ...}
```

### Frame structure (after 5-min captures of both Cookies)

Long stationary captures of both Cookies through the rtl_433 decoder
yielded 20 frames (awesome you) and 31 frames (safe song). Grouping by
byte 0 and then by the magic at bytes 2–4 reveals **two dominant
patterns shared by both Cookies**:

#### Pattern X — "presence" (≈75% of frames)

```
byte:  0       1   2   3   4    5   6   7   8    9   10   11..end
       [type]  1E  E2  65  12   [ — device-bytes — ]  ?  D2  [seq+CRC]
```

- byte 0: frame type, observed `0xF4` and `0xEC` (and rarely `0xE8` etc)
- bytes 1–4: `1E E2 65 12` — protocol header, same across both Cookies
- bytes 5–8: per-Cookie constant — **safe song = `EA DF 32 FF`**,
  **awesome you = `9A 94 3E C2`**
- byte 9: mostly `0x7D` for awesome you, mix of `7D / 79 / FF` for safe
  song
- byte 10: mostly `0xD2`
- last 2–3 bytes: change every frame → likely sequence counter + CRC

#### Pattern α — "alt" (≈15% of frames)

```
byte:  0       1   2   3   4    5   6   7   8    9   10   11..end
       [type]  1E  C4  CA  25   [ — device-bytes — ]  FB  A4/A5  [seq+CRC]
```

- byte 0: `0xF4` mostly (`0xF0` seen once)
- bytes 2–4: `C4 CA 25` — protocol header, same across both Cookies
- bytes 5–8: per-Cookie constant — **safe song = `D5 BE 65 FE`**,
  **awesome you = `35 28 7D 84`**
- byte 9: always `0xFB` (constant across both Cookies)
- byte 10: `0xA4` or `0xA5` (constant across both Cookies)
- last 2–3 bytes: change every frame → sequence + CRC

#### Per-Cookie identifier bytes (positions 5–8)

| Pattern | safe song | awesome you |
|---|---|---|
| X (presence) | `EA DF 32 FF` | `9A 94 3E C2` |
| α (alt)      | `D5 BE 65 FE` | `35 28 7D 84` |

These four-byte fields are **completely stable within each Cookie's
frames of the same pattern**, and cleanly different between Cookies.
But the Cookie's "X bytes" and "α bytes" don't match each other — so
bytes 5–8 don't carry a literal device-ID number. Either:

- The four bytes are an identifier passed through CC1101 PN9 whitening
  at a different phase per frame-type, producing different masked
  values for the same underlying ID, or
- Pattern α is a sensor-snapshot frame whose middle bytes carry actual
  sensor data (accel/temperature) — in which case the bytes won't
  match between patterns even with whitening off.

The flip-test and temperature-ramp experiments queued below will
distinguish these.

Other observations:

- `0x1E` at byte 1 is constant in both patterns and both Cookies but is
  not the length byte (decoded frames are ~14 bytes after sync, not 30).
- rtl_433 reports each frame as 125–129 bits (≈15.6–16.1 bytes including
  sync). The "longer bursts" we saw earlier were two frames back-to-back.
- Safe song transmits noticeably faster (~10 s between bursts) than
  awesome you (~15 s). Probably because the safe-song capture involved
  more handling — accelerometer-wake bumps the rate. Confirms the
  spec sheet's "mobile cookies drain battery faster" line.

### Tooling

- `scratch/bucket_bursts.py` — bin rtl_433 detections into time windows
  defined by a `timeline.txt` file. Used for the shake-test triage.
- `scratch/cookie_signature.py` — extract per-burst RSSI, SNR, dominant
  pulse width, frequency offset, file path. Used to find the
  Cookie-vs-everything-else clusters (see "Two FSK clusters" — same RSSI,
  same pulse width, same near-zero frequency offset across all Cookie
  bursts).
- `scratch/decode_fsk.py` — naive FSK demod (no timing recovery). Useful
  for first-look at a single capture but loses byte alignment by 1 bit
  occasionally.
- `scratch/decode_fsk_v2.py` — preamble-anchored demod with sub-sample
  zero-crossing detection. Reliably finds `0xD391` in 4/5 captures.
- `scratch/align_frames.py` — runs v2 across all candidate files and
  produces the column alignment + per-byte entropy table above.
- `scratch/analyze_frames.py` — reads rtl_433 `hits.json` output from a
  capture session, groups frames by byte 0, and reports per-position
  entropy (constant vs varying). The right tool now that rtl_433 itself
  is doing the decode; supersedes the homebrew demod scripts above.

### Capture-time gotcha

In a busy 915 MHz environment, rtl_433's auto-gain saturates and Cookie
bursts get lost in the SNR noise of nearby ISM-band devices. Lock the
RTL-SDR gain low (`-g 0` for a Cookie touching the antenna) so the
Cookie's RSSI clearly dominates everything in the room.

## Mother teardown (June 30 2026)

Bench teardown photos in `teardown/mother/`. Enclosure came apart as a
snap-fit around the bottom seam — no visible screws on this hardware
revision (the FCC-photographed unit had a rubber base with hidden
screws; production hardware simplified to plain snap-fit).

### Main PCB silicon

Readable from the teardown close-ups:

| Ref | Marking (partial) | Identification | Purpose |
|---|---|---|---|
| main MCU | `PIC32` (large TQFP) | Microchip PIC32-series MIPS MCU | Runs WiFi/Ethernet uplink + cloud logic |
| `U5` | `Spansion FL064PIF` (SO-16) | Spansion / Cypress **S25FL064P** — 64 Mbit (8 MB) SPI serial flash | Firmware + web assets storage |
| `U16` | `DAC8100` (QFN) | Audio DAC | Drives the Mother's alert sounds |
| `Y6` (near MCU) | `8.000 MHz` HC-49 | Crystal | PIC32 main clock |
| `Y3` (near flash) | `50.000 MHz` SMD | Crystal | Ethernet PHY clock |
| bulk cap | `1000 µF 10 V RVT` electrolytic | — | Power rail bulk decoupling |

### Wireless daughtercard

Small separate PCB, connects to the main board via a 7-pin ribbon
cable (visible in `teardown/mother/2026-06-30_170923.jpg`). Carries
the 915 MHz radio + trace antenna. The chip markings on the current
photos are at too shallow an angle to read; a straight-on close-up
is the next info gap. Given the Cookie is CC430F5137, expected
options are:

- Another **CC430F5137** (SoC, MSP430 + CC1101) — most likely, keeps
  the firmware toolchain symmetric between endpoints
- Bare **CC1101** driven by a small MSP430 or PIC — possible but
  would imply two different codebases; less likely

### Debug / service headers

- `J10` — 4-hole through-hole footprint on the **left edge of the
  main PCB, near the 8.000 MHz crystal** (front side, see
  `teardown/mother/2026-06-30_170947.jpg`). 4-pin geometry is the
  usual `VCC / TX / RX / GND` UART footprint. **Best guess for the
  Mother's debug UART console.** Highest-value probe target.
- `J12` — 6-hole footprint on the **back of the main PCB, adjacent
  to the Ethernet daughtercard mating pins**. Almost certainly the
  Ethernet mezzanine interface, not a service header.
- `J13` — 2-pin populated JST on the back of the main PCB. Guessed
  to be a factory-reset button or spare I/O.

Confirming J10's UART pinout before wiring a serial adapter:

1. Power off. Continuity-check each J10 pin to any obvious ground
   (large plane, bulk-cap ground pin). The one that beeps is `GND`.
2. Power on. DC-measure the other three pins. `VCC` sits at 3.3 V.
   The remaining two are `TX` / `RX`.
3. `TX` shows visible voltage dips on a multimeter during boot (the
   Mother is transmitting characters). `RX` idles at 3.3 V.
4. Adapter-RX to Mother-TX, adapter-GND to Mother-GND, `screen
   /dev/tty.usbserial-XYZ 115200` (or 57600 / 9600), reset the
   Mother, and boot output should appear.

### Sub-boards

- `LBQ-603-D-V1.1` (dated 2013-10-25) — small PCB with dome contacts;
  the top-side capacitive-touch button + LED "face" of the Mother
- One or two small **speaker/transducer** boards driving the alert
  sounds via the DAC8100

### UART console output (fw v398)

J10 confirmed as `VCC (square pad) / GND / RX / TX` at 115200 8N1.
Full boot log in `teardown/mother/boot-log-fw398.txt`. Highlights:

```
#-0- System starting
#-0- Firmware Version: 398
#-0- Init SENSE Hardware
#-0- Init I2C
#-0- Init LED Driver
#-0- Init MEM
#-0- Memory JedecID: 10216
#-0- Init DAC Audio
#-0- Init Touch sensor
#-2006- Run Animation "start"
#-9774- Run Animation "nonetwork"
#-9778- #Starting TCP/IP...
#-9670- #Starting SimpliciTI...
#-9673- #Starting main loop...
#-9676- #New IP Address: 192.168.2.165
#-14183- #Reset RF...
#-14185- #Starting SimpliciTI...
```

Two conclusions worth their own subsections:

#### The RF protocol is **TI SimpliciTI**

The `Starting SimpliciTI...` and `Reset RF...` lines are decisive.
**SimpliciTI is Texas Instruments' proprietary low-power sub-GHz
network protocol** — designed for CC1101 / CC2500 radios, targeted
at exactly this class of star-topology sensor network (one Access
Point + up to N End Devices). Released with reference source and
app-note documentation (TI documents `SLAA344`, `SLA485`) around
2008–2013 before TI deprecated it in favor of newer stacks. Public
source and docs are still available.

Big implications:

- **The frame layout we RE'd byte-by-byte is a documented
  SimpliciTI packet**, not sen.se's invention. Bytes 0–4 are almost
  certainly SimpliciTI's network header (packet type + length +
  peer link ID); bytes 5–10 include the SimpliciTI Peer Link
  address + sequence number.
- The Cookie is a SimpliciTI End Device; the Mother is the Access
  Point.
- **Building our own AP** using TI's reference implementation on a
  Pi + CC1101 (or a MSP430 devboard) would let us **join the
  network as if we were a Mother** and use SimpliciTI's native
  request/response API to poll Cookies for stored data — the
  shortest path to bed-temperature-in-HA.

This obsoletes most of the "reverse engineer the Mother's downlink
by dumping its firmware" work — with SimpliciTI as the substrate,
the protocol is documented, the source is public, and we can just
write an AP that speaks the same stack.

#### Mother boots happily with no cloud

- Comes up cleanly in ~9.7 s to `Starting main loop...` even with
  **Ethernet unplugged**. The `New IP Address: 192.168.2.165` line
  is NOT a DHCP-obtained address — no link, no DHCP. Either NVRAM
  cached from a prior deployment, or a firmware fallback value.
  Either way, SimpliciTI initialises independently of the WAN side.
- SimpliciTI init happens right after the TCP/IP stack comes up,
  and re-init ("Reset RF...") starts a few seconds later — the
  Mother runs indefinitely trying to relink to Cookies even with
  no cloud reachable. It just loops the `"nonetwork"` LED animation
  because the cloud-uplink health check fails.
- Useful for future testing: leave the Mother powered next to an
  SDR and it'll keep re-initing SimpliciTI and re-issuing whatever
  handshake frames it sends to Cookies — a free source of live
  Mother-side downlink captures.

#### Flash JedecID cross-check

`Memory JedecID: 10216` decodes as:
- Manufacturer `0x01` — Spansion / Cypress
- Device `0x0216` — S25FL064P family

Independent confirmation of the chip-marking read. The dump-path
below still applies.

### Firmware extraction path

The S25FL064P is a standard SPI serial flash with **no chip-level
read protection**. It can be dumped in-circuit:

```bash
# with a CH341A programmer + SOIC-16 test clip clipped onto U5
flashrom -p ch341a_spi -c S25FL064P -r mother_flash.bin
```

Prerequisites:

- Mother unplugged (so the PIC32 doesn't fight the programmer on the
  SPI bus). The clip's 3.3 V line powers the flash chip alone.
- CH341A programmer confirmed at 3.3 V (some clones ship 5 V by
  default — check before clipping)

What we expect in the dump:

- PIC32 MIPS application firmware (probably raw, unencrypted — this
  era + this class of device rarely bothered with flash encryption)
- Web / dashboard assets that the Mother served locally
- Cookie pairing state — which 24-bit Cookie IDs it knows, plus any
  keys/nonces used in the Mother↔Cookie downlink
- **The downlink frame format** — the Mother has to construct these
  frames, so the layout is in this firmware. This is the missing
  piece we couldn't extract passively.

If the dump is encrypted after all, the fallback is to attach a UART
adapter to `J12` and watch the Mother's serial console during a
pairing/query attempt.

## Experiments run

- **Stationary 5-min baselines on all three Cookies** (`captures/<name>-long/`).
  Established the two-pattern (X / α) frame structure and identified
  bytes 6–8 of pattern X as the **24-bit per-Cookie device ID**
  (`df 32 ff` / `94 3e c2` / `9b 01 cf` for safe song / awesome you /
  organic macarons). Byte 5 is shared between awesome you and organic
  macarons (`0x9a`) but differs for safe song (`0xea`) — likely a
  hardware-batch or firmware-revision byte.
- **Flip test on safe song** (`captures/safe-song-flipped/`):
  **inconclusive on accel.** Bytes 5–10 unchanged across orientations
  in both patterns X and α. Only the trailing 2 bytes (sequence + CRC)
  moved, as expected of any frame whose body shifted.
- **Palm-warmth test on organic macarons** (`captures/organic-macarons-palm/`):
  **inconclusive on temperature.** Pattern X bytes 0–10 are *byte-for-byte
  identical* between room baseline and palm-warmed capture. Pattern α
  bytes 5–8 also unchanged.

### What both null results imply

The Cookie's beacons don't appear to carry live accelerometer or
temperature data. This fits the sen.se spec sheet's claim that Cookies
can "stock up to 15 days of data when away from Mother's range" — sensor
history is buffered locally and uploaded *on request* by Mother's
downlink, not pushed in presence beacons. A purely passive sniffer
can identify which Cookie is broadcasting (device ID) but can't read
its sensor values.

To actually read bed temperature, the receiver has to **transmit**: emit
the Mother-side query, then decode the Cookie's data-frame reply. That's
a different hardware class than RTL-SDR + rtl_433 (RX only) — it needs
a CC1101-class transceiver wired to a host (Pi + CC1101 module, ESP32
+ CC1101, or LilyGO T-Embed CC1101 — all options listed under "Phase 4:
bridge to Home Assistant" above already support TX).

### Open work to enable read-out

Now that we know the RF protocol is **TI SimpliciTI** (see UART boot
log), the shortest path becomes:

**A. Build a SimpliciTI Access Point that speaks to Cookies:**

1. **Pull TI's SimpliciTI reference implementation** (last public
   drop was `SimpliciTI-CCS-1.2.0` or similar; still archived in
   TI's forums and elsewhere online).
2. **Configure it to run on a CC1101 module** wired to a Pi (or an
   ESP32, or a T-Embed CC1101) — SimpliciTI's HAL is portable.
   Match the Cookie's PHY: 915 MHz US band, 100 kbps GFSK, sync
   `0xD391`, whatever channel/PAN-ID we observe live.
3. **Compare our observed frames** to SimpliciTI's documented header
   layout to figure out which SimpliciTI application-layer message
   the Cookies send (probably a periodic `Link_Send` with a small
   payload, plus responses to `Poll`).
4. **Issue the poll from our AP** and receive the Cookie's
   stored-data reply. Presumably temperature + accel history are in
   there — that's what Mother pulled to display.

**B. Sniff a real Mother↔Cookie exchange** to shortcut step 3:

1. Sit the Mother next to an RTL-SDR (it happily loops
   `Reset RF... / Starting SimpliciTI...` without cloud).
2. Capture both sides at 915 MHz. The Mother's downlink frames
   reveal exactly which SimpliciTI message it issues and how it
   addresses a specific Cookie.
3. That collapses step 3 above from "read SimpliciTI docs" to
   "copy what the Mother did."

**C. Firmware dump as a fallback / verification** (see
"Firmware extraction path" below): dump the SPI flash if steps
A or B stall on any ambiguity; pattern-match by the constants
we know (`0xD391`, `1E E2 65 12`, `C4 CA 25`) to find the
downlink-frame construction code.

**Then, common to all three:**

4. **Plumb into HA** as previously planned — rtl_433 alone can't do
   this (no TX), so use T-Embed CC1101 + ESPHome, or Pi + CC1101
   with a small SimpliciTI driver.

## CC1101 PN9 data-whitening — the missing decode step

sen.se left CC1101's default `PKTCTRL0.WHITE_DATA = 1` enabled. That
means every "data" byte on the air (everything between the length
byte and the CRC) is XORed with a fixed pseudo-random sequence
generated by a 9-bit LFSR (polynomial `x⁹ + x⁵ + 1`, seed `0x1FF`).
The PN9 stream starts `FF E1 1D 9A ED 85 33 24 EA 7A D2 39 …`.

Until we apply this XOR pass, every field we read is scrambled. Once
we do, the SimpliciTI framing lines up cleanly and — importantly —
**the "encryption bit" we thought was set in the PORT byte is actually
0 on every Cookie frame**. The frames are plaintext. Sen.se's Cookies
don't use SimpliciTI's XTEA layer at all.

Applied via `scratch/cc1101_dewhiten.py` and `scratch/parse_frames.py`.

Two independent structural confirmations that the whitening pass is
correct, not just parsimonious:

1. **XOR determinism.** The 4 bytes `1e e2 65 12` at positions 1–4 XOR
   with PN9's first 5 output bytes to give exactly `ff ff ff ff` — the
   SimpliciTI broadcast DSTADDR. This holds for every Cookie's every
   frame at those positions. PN9 is a fixed deterministic sequence,
   so this is either the intended decode or a fantastic coincidence.
2. **Link Token match.** Every port-3 (Join) frame's payload, after
   dewhitening, contains `08 07 06 05` at bytes 3–6 of the payload —
   exactly where SimpliciTI Spec Table 8 defines the Link Token field.

Example — organic macarons post-sync data:

```
whitened:   f4 1e e2 65 12 9a 9b 01 cf 7d d2 cc 33 14
dewhitened: 0b ff ff ff ff 1f a8 25 25 07 00 f5 43 83
             ^  ^^^^^^^^^^^ ^^^^^^^^^^^ ^^ ^^ ^^^^^^^^
           len      DSTADDR    SRCADDR PORT DI  payload
                  (broadcast)                  (3 bytes)
```

## Frame mapping against SimpliciTI spec

Reading `simpliciti/simpliciti-1.2.0-mspgcc/Documents/SimpliciTI
Specification.pdf` (Section 5, Figures 7-8, Tables 1-3) and applying
after PN9 de-whitening:

Reading `simpliciti/simpliciti-1.2.0-mspgcc/Documents/SimpliciTI
Specification.pdf` (Section 5, Figures 7–8, Tables 1–3) and lining up
against our decoded Cookie frames:

The general SimpliciTI-over-CC1101 frame (per Section 5 / Figure 7) is:

```
PREAMBLE | SYNC | LENGTH | DSTADDR(4) | SRCADDR(4) | PORT | DEVICE INFO | App Payload | FCS
```

(MISC is "may be absent" for CC1101 and sen.se leaves it absent.
TRACTID is not present in the frames we see either — sen.se's variant
elides it.)

Applied to a de-whitened organic-macarons PLL frame
`0b ff ff ff ff 1f a8 25 25 07 00 f5 43 83`:

| pos  | field           | value          | interpretation                                        |
|------|-----------------|----------------|-------------------------------------------------------|
| 0    | **LENGTH**      | `0x0B` = 11    | bytes after LENGTH (13 total minus this byte = 12) ✓  |
| 1–4  | **DSTADDR**     | `ff ff ff ff`  | **broadcast address** — Cookies broadcast to any AP   |
| 5–8  | **SRCADDR**     | `1f a8 25 25`  | organic macarons' 4-byte SimpliciTI address           |
| 9    | **PORT**        | `0x07`         | bit 7=0 not-forwarded, **bit 6=0 no encryption**, port 7 = **PLL** |
| 10   | **DEVICE INFO** | `0x00`         | End Device, controlled listen, no ack req, hop 0      |
| 11–13 | **App Payload** | `f5 43 83`     | 3-byte PLL payload (counter + short data)             |
|  —   | FCS             | (stripped by CC1101 HW) | 16-bit CRC                                   |

The de-whitened SRCADDRs (per-Cookie 4-byte SimpliciTI addresses):

| Cookie           | SimpliciTI SRCADDR  |
|------------------|---------------------|
| safe song        | `6f ec 16 15`       |
| awesome you      | `1f a7 1a 28`       |
| organic macarons | `1f a8 25 25`       |

awesome you and organic macarons have consecutive `1f a7 …` / `1f a8 …`
prefixes — same factory batch. safe song is from a different batch.

### Frame types observed

Cookies send two distinct types of broadcasts:

- **Port 7 (PLL)** — 11-byte frame with a **3-byte payload**. Every
  ~15 s. This is the "presence beacon" we've been chasing. Payload
  is a counter + short data byte + one more byte (function unclear,
  possibly a checksum or state).
- **Port 3 (Join)** — 19-byte frame with an **11-byte payload**
  matching SimpliciTI Spec Table 15 (Join Client Side Payload) with
  a sen.se-specific 1-byte prefix and 2-byte suffix:
  ```
  [prefix] [Request=0x01] [TID] [Join Token=08 07 06 05]
           [NumConn=0x02] [ProtoVer=0x02] [FCS(2)]
  ```
  The Cookies broadcasting on this port means **they are currently
  unlinked** — an End Device that has successfully joined an AP stops
  Join-broadcasting and switches to unicast. Every ~1 minute the
  Cookies re-broadcast Join looking for a Mother to reply.

  The **`08 07 06 05` Join Token is sen.se's network-wide shared
  secret** — every sen.se Cookie and Mother carries it. Anyone with
  a SimpliciTI-capable radio and this token can pretend to be a
  legitimate sen.se network member.

  Expected Mother reply per Spec Table 16 (Join Server Side Payload):
  ```
  [Req Reply=0x81] [TID echoed] [session LinkToken=4B] [FUNC/LEN=1B] [Key=N bytes]
  ```
  Unicast back to the Cookie's SRCADDR. Capturing this frame is the
  next milestone — see "Open work to enable read-out" below.

Both frame types are **completely plaintext** — no XTEA layer is
active.

### Other SimpliciTI devices in range

`scratch/srcaddr_recurrence.py` cross-references SRCADDRs across all
capture sessions. Addresses seen in ≥2 independent sessions are
almost certainly real devices; addresses seen once with a single
frame are bit-slip artifacts of rtl_433's demod.

Real neighbors (recur across multiple sessions):

- `50 8d 41 14` — 7 frames across 2 safe-song sessions (ports 1 & 9,
  fwd=1: this device is acting as an Access Point or Range Extender)
- `b0 1b 59 6e` — 3 frames across 2 awesome-you sessions (port 1
  Ping, fwd=1)
- `b0 05 27 74` — 3 frames across 2 organic-macarons sessions
  (port 9 fwd=1)
- `4f 16 f1 54` — 2 frames across 2 safe-song sessions

So there are roughly 3–4 other active SimpliciTI devices in RF range,
not seven — the rest were rtl_433 decoding noise. Three of the four
send *forwarded* frames, which means those are Access Points or
Range Extenders (i.e., Mothers or similar), not raw Cookies.

Also worth noting: `6f ec 16 14` looks like a real "other device" but
is actually a 1-bit slip of safe song's own `6f ec 16 15` — appears in
the *same* Cookie's sessions where safe song was live. Same story for
`6f ed 41 14` and its variants: bit slips of `50 8d 41 14`.

## Open questions

- **Confirm the LENGTH / MISC byte location.** The first byte `0xf4`
  we're currently reading as the start of DSTADDR may actually be a
  radio-inserted MISC or LENGTH byte with DSTADDR starting at position
  1. Cross-check by decoding a Mother-side frame (once we sniff one) —
  its DSTADDR should be a Cookie's address, which will disambiguate.
- **Whether sen.se used the default SimpliciTI network key.** If yes,
  passive decryption from `simpliciti/` samples is possible. If not,
  key extraction needs the SPI-flash dump.
- **Cookie SimpliciTI address byte order** (little-endian vs
  big-endian). SimpliciTI spec 4.8 states multi-byte numbers are
  little-endian, so the printed byte order and the numeric device ID
  may need reversal for cross-reference.
- **Confirm bytes-5–7-per-Cookie shared factory batch** by scanning
  the third-party Cookie market for more devices.
- **The rare `d3` / `a7` frame types.** May be SimpliciTI Link (port
  0x02) or Join (port 0x03) frames sent when a Cookie is trying to
  (re-)associate.
- **EU 868 MHz frame layout** — assumed identical (same CC430F5137
  and same SimpliciTI stack, just moved to 868 MHz) but not verified.
- **Flipper Zero support for SimpliciTI.** The Flipper's sub-GHz radio
  is a CC1101, so raw capture at 915 MHz should be feasible. Investigate:
  - Whether the Flipper can decode / recognize SimpliciTI framing
    (matching `0xD391` sync, 100 kbps GFSK) even without decrypting
  - Whether an existing community app can dissect SimpliciTI packets
  - Even a "detect Cookies nearby by SRCADDR" identifier-only mode
    would be useful for coverage checks without dragging out an SDR.

## References

- FCC Part 15.249 limits: https://www.ecfr.gov/current/title-47/section-15.249
- URH (Universal Radio Hacker): https://github.com/jopohl/urh
- rtl_433: https://github.com/merbanan/rtl_433
- LilyGO T-Embed CC1101 (ESP32-S3 + CC1101 board): https://www.lilygo.cc/products/t-embed-cc1101
- dbuezas/esphome-cc1101 (ESPHome external_component): https://github.com/dbuezas/esphome-cc1101
- rtl_433_ESP (ESP32 port of rtl_433 decoders): https://github.com/NorthernMan54/rtl_433_ESP
- OpenMQTTGateway: https://docs.openmqttgateway.com/
- ccarlo64/freemother (cloud emulator, no temp support): https://github.com/ccarlo64/freemother
- Forum thread that pointed at freemother: https://nabaztag.forumactif.fr/t15361
- TI CC1101 datasheet: https://www.ti.com/product/CC1101
