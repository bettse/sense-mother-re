# sen.se Mother / Cookie — Reverse Engineering

Reviving the defunct sen.se Mother hub + Motion Cookie sensors (2013–2017,
company gone) enough to talk to them without the dead `in.sen.se` cloud.

## 🚦 Project status

📻 **RF layer decoded.** Cookies talk **TI SimpliciTI over CC1101** at
915 MHz (US) / 868 MHz (EU), 100 kbps 2-GFSK, sync word `0xD391`,
PN9-whitened, **no encryption**. Every frame captured to date is
plaintext once the PN9 XOR is applied.

🍪 **All Cookies are the same hardware.** One SKU, one silicon
(**TI CC430F5137**: MSP430 MCU + CC1101 radio in one QFN). What
sen.se marketed as "temperature / sleep / presence" Cookies were 100 %
cloud-side interpretation — they all send the same beacons.

👩 **Mother teardown + firmware map done.** UART console pinned down
(J10, 115200 8N1). Boot log names SimpliciTI directly. External SPI flash
dumped — turns out it's just config + LED animations + WAV alerts; the
PIC32 firmware itself lives in the MCU's internal flash and would need
ICSP to extract (**not attempted, not needed**).

🎯 **Blocker: sensor readings need a TX-capable receiver.** Passive-only
sniffing gets you Cookie presence + device ID but not temperature. The
Cookies buffer sensor data until an Access Point (Mother) polls them.
To read bed temperature we have to **speak SimpliciTI back at them** —
join them to our own AP.

🛠️ **Next step: build a SimpliciTI AP** on any CC1101-capable ESP32
board (see [CC1101 hardware options](#cc1101-hardware-options)),
port TI's reference AP code, reply to the Cookies' unencrypted Join
broadcasts (network-wide token `08 07 06 05`, in the clear on every
frame), and bridge the resulting sensor traffic to Home Assistant as
BTHome BLE advertisements.

🕵️ **Prior art:** Seekintoo's 2017 iSmartAlarm break attacked the same
protocol on a different device (CC1110-based, but same SimpliciTI +
PN9 stack). Their RX pipeline is vendored under `prior-art/iSmartAlarm/`
as a reference.

### 📁 Repo layout

```
sense-mother-re/
├── README.md                              this file
├── fetch.sh                               re-pull FCC exhibits idempotently
├── sen-se-mom4co-us-specsheet-12.pdf      original sen.se marketing spec
├── fcc/{cookie,mother}/                   FCC exhibits (photos, RF report)
├── teardown/mother/                       bench teardown photos + boot log +
│   ├── flash-fw398.bin                    full 8 MiB SPI flash dump
│   └── flash-extracted/                   config, animations, WAV alerts
├── captures/                              rtl_433 sessions per-Cookie
├── scratch/                               analysis / extraction scripts
├── simpliciti/                            vendored TI SimpliciTI 1.1.1 + 1.2.0
└── prior-art/iSmartAlarm/                 Seekintoo's SimpliciTI attack
```

## 📻 RF quick reference

| | |
|---|---|
| **Chip (Cookie)** | TI **CC430F5137** (MSP430 + CC1101, one QFN) |
| **Chip (Mother)** | Microchip PIC32 (main) + wireless daughtercard, likely CC430 too |
| **Band** | 915 MHz (US, FCC Part 15.249) / 868 MHz (EU) |
| **Modulation** | 2-GFSK, 99.97 kbps (CC1101 "100 kbps" preset), deviation ~±50 kHz |
| **Sync word** | `0xD391` (CC1101 default) |
| **Data whitening** | CC1101 PN9, seed `0x1FF`, poly x⁹ + x⁵ + 1 |
| **Encryption** | None. Frames are plaintext once dewhitened. |
| **Protocol** | TI SimpliciTI (network layer) |
| **Cookie beacon period** | ~15 s (port 7 PLL); ~1 min (port 3 Join) |
| **Battery** | CR2016 (4 mm Cookie thickness rules out CR2032) |

## 🧩 SimpliciTI frame layout

After PN9 dewhitening the frame follows the SimpliciTI spec
(`simpliciti/simpliciti-1.2.0-mspgcc/Documents/SimpliciTI Specification.pdf`,
Section 5, Figures 7–8, Tables 1–3):

```
LENGTH | DSTADDR(4) | SRCADDR(4) | PORT | DEVICE INFO | App Payload | FCS
```

sen.se's variant omits SimpliciTI's optional MISC and TRACTID fields.
Both frame types observed on the air are plaintext (PORT bit 6 = 0).

### 🍪 Cookie beacon (port 7 "PLL")

11-byte frame, 3-byte app payload. Example (organic macarons):

```
whitened:   f4 1e e2 65 12 9a 9b 01 cf 7d d2 cc 33 14
dewhitened: 0b ff ff ff ff 1f a8 25 25 07 00 f5 43 83
             ^  ^^^^^^^^^^^ ^^^^^^^^^^^ ^^ ^^ ^^^^^^^^
           len   DSTADDR      SRCADDR   PORT DI  payload
                (broadcast)                     (3 bytes)
```

The 3-byte payload is a slowly-varying counter + one status byte —
too small to carry temperature or accel data, which confirms sensor
readings must be gated behind a Mother poll.

### 🔗 Cookie Join broadcast (port 3)

19-byte frame, 11-byte app payload matching SimpliciTI Spec Table 15
with a 1-byte prefix + 2-byte suffix:

```
[prefix] [Request=0x01] [TID] [Join Token=08 07 06 05]
         [NumConn=0x02] [ProtoVer=0x02] [FCS(2)]
```

`08 07 06 05` is the **sen.se network-wide shared secret** — every
Cookie and every Mother carries it. Any SimpliciTI-capable radio that
knows this token can pose as a legitimate sen.se AP.

### 🏷️ Known SRCADDRs (this project's Cookies)

| Nickname          | SimpliciTI SRCADDR    |
|-------------------|-----------------------|
| safe song         | `6f ec 16 15`         |
| awesome you       | `1f a7 1a 28`         |
| organic macarons  | `1f a8 25 25`         |

awesome you + organic macarons share a `1f a7…` / `1f a8…` prefix —
same factory batch. safe song is a different batch.

`scratch/srcaddr_recurrence.py` cross-references SRCADDRs across
sessions to distinguish real neighbor devices from rtl_433 bit-slip
artifacts. Real neighbors in RF range: `50 8d 41 14`, `b0 1b 59 6e`,
`b0 05 27 74`, `4f 16 f1 54` — three of the four send forwarded
frames, so those are APs (Mothers or Range Extenders), not raw Cookies.

## 🔬 Capturing and decoding

rtl_433 handles the PHY natively with a one-line flex decoder:

```bash
rtl_433 -f 915M -s 2400000 -g 0 \
        -X 'n=cookie,m=FSK_PCM,s=10,l=10,r=400,preamble=d391' \
        -F json:hits.json -F log:rtl433.log
```

- `-f 915M` — US band; use `868M` for EU
- `-g 0` — minimum LNA gain; required if the Cookie is touching the
  antenna. Higher gain is fine at room scale.
- `preamble=d391` — CC1101 default sync, used to lock byte alignment

Each hit lands in `hits.json` as `d391...` — strip the sync, then apply
the PN9 XOR (`scratch/cc1101_dewhiten.py`), then parse per the frame
layout above (`scratch/parse_frames.py`).

## 👩 Mother teardown

Photos in `teardown/mother/`. Snap-fit enclosure (no visible screws).

**Silicon (main PCB):**

| Ref | Chip | Purpose |
|---|---|---|
| main MCU | Microchip PIC32 (large TQFP) | WiFi/Ethernet uplink + cloud logic |
| `U6` | Spansion **S25FL064P** (SO-16) | 8 MB SPI flash — config + assets |
| `U16` | **DAC8100** (QFN) | Audio DAC for alert sounds |
| `Y6` | 8.000 MHz HC-49 | PIC32 clock |
| `Y3` | 50.000 MHz SMD | Ethernet PHY clock |

**Debug headers:**

| Header | Location | Purpose |
|---|---|---|
| `J10` | Left edge, front, near Y6 | **UART console, 115200 8N1** — pinout `VCC (square pad) / GND / RX / TX` |
| `J12` | Back, near Ethernet daughtercard | Ethernet mezzanine interface (not a service port) |
| `J13` | Back, 2-pin JST | Guessed factory-reset button |

**Wireless daughtercard** rides on a 7-pin ribbon cable off the main
PCB. Carries the 915 MHz radio + trace antenna. Chip markings not yet
readable in the current photos; a straight-on close-up is the last
info gap.

### 💾 UART boot log (fw v398)

Full log at `teardown/mother/boot-log-fw398.txt`. The decisive lines:

```
#-0- System starting
#-0- Firmware Version: 398
#-0- Init SENSE Hardware
#-0- Memory JedecID: 10216
#-2006- Run Animation "start"
#-9670- #Starting SimpliciTI...
#-9676- #New IP Address: 192.168.2.165
#-14185- #Starting SimpliciTI...
```

- `Starting SimpliciTI...` is what tells us the protocol.
- Mother boots cleanly to `main loop` in ~9.7 s with Ethernet unplugged.
  `New IP Address` with no link is either NVRAM-cached or a firmware
  fallback — SimpliciTI comes up regardless. Left powered next to an
  SDR, the Mother re-runs `Reset RF... / Starting SimpliciTI...`
  indefinitely, a free source of live Mother-side downlink captures.
- Memory JedecID `10216` = `01 02 16` → Spansion S25FL064P, confirming
  the chip-marking read.

### 🧯 SPI flash dump (fw v398)

Full 8 MiB dump at `teardown/mother/flash-fw398.bin`. Dumped in-circuit
with a **Flipper Zero + SOIC-16 clip** using the SPI Mem Manager app
(S25FL064P profile).

**Gotcha:** the clip's 3.3 V pin **backfeeds through the shared power
rail and boots the whole board**. The PIC32 then drives SPI in parallel
with the dumper and corrupts the read. Fix: hold the PIC32's **MCLR pin
to GND** during the dump (pin 7 on the top edge of the 64-pin TQFP, six
pins to the left of the corner dimple). Chime + LED animation stop when
reset is held.

**The PIC32 firmware is NOT on this flash.** 97.5 % of the dump is
`0xFF`; only ~213 KiB of real content, and zero occurrences of the
sync word `0xD391`, Join Token, or any Cookie SRCADDR. The PIC32's
application code lives in its **internal** program flash. This
external SPI is just an asset store:

| Region | Size | Contents |
|---|---|---|
| `0x000000-0x000529` | 1.3 KiB | Boot config + two lookup tables |
| `0x0E0000-0x0E21D6` | 8.7 KiB | 11 LED animation JSON blobs |
| `0x200000-0x2369B4` | 223 KiB | 5 WAV alert sounds (16 kHz 16-bit mono PCM) |
| everything else | ~7.8 MiB | Blank (`0xFF`) |

The boot config carries two 24-byte-record arrays mapping state names
→ `(size, offset)` for both the WAVs and the animations. Records:

```
offset  field
 0..15  name  (null-terminated ASCII)
16..19  size  (little-endian u32)
20..23  offset (little-endian u32)
```

**5 sounds (table at `0x0081`)** — 4 of the 5 are `in.sen.se` cloud-uplink
state cues, one is the boot chime:

| Name | Size |
|---|---|
| `start` | 76,044 B (boot chime) |
| `registration` | 89,250 B (cloud register OK) |
| `noregistration` | 24,254 B (register failed) |
| `nonetwork` | 12,122 B (no LAN link) |
| `noplateform` | 21,428 B (cloud unreachable) |

**11 animations (table at `0x0355`)**: `start`, `wakeup`, `sleep`,
`idle`, `demo`, `newstate`, `upgrading`, `registration`,
`noregistration`, `nonetwork`, `noplateform`. Each is a JSON array of
`{"type":"light","sequence":[{"leftEye":…,"rightEye":…,"smile":…,
"transition":"fade",…}]}` steps. Only `start` mixes in a
`"type":"sound"` step (`soundId:"start"`).

**Take-away:** the Mother's SimpliciTI downlink code cannot be
recovered from this flash — it's inside the PIC32. Extracting it would
need ICSP + unset code-protect fuses. Not attempted, and **not needed**
to build a SimpliciTI AP: the protocol is public, TI's reference source
is vendored under `simpliciti/`, and the sen.se specifics (Join Token
`08 07 06 05`, sync word `0xD391`, PN9 whitening, no encryption) are
already RE'd from RF captures.

## 🚧 What doesn't work (yet)

Two negative-result bench tests, both consistent with the SimpliciTI
model above:

- **Cookie flip test** — accelerometer orientation changes produce **no
  byte changes** in the 3-byte port-7 payload.
- **Cookie palm-warming test** — none of the 3 payload bytes track
  temperature between room and palm captures.

The 3-byte PLL payload is too small to hold either sensor stream. Both
readings must be buffered locally until Mother polls the Cookie — which
requires TX. RTL-SDR + rtl_433 alone can't do this.

## 🎯 Getting to bed-temperature-in-HA

The shortest remaining path is to **become the Mother**. The Cookies
Join-broadcast every ~1 min with `08 07 06 05` in the clear; anything
that replies with a valid SimpliciTI Join Server Side payload
(Spec Table 16) gets them to link.

Steps:

1. Configure a CC1101 module on the AP host to sen.se's PHY: 915 MHz,
   100 kbps GFSK, sync `0xD391`, PN9 whitening ON, variable-length
   packets, no encryption.
2. Listen for port-3 Join frames containing `08 07 06 05` at payload
   offset 3.
3. Send the unicast reply per SimpliciTI Spec Table 16:
   `[Req Reply=0x81] [TID echoed] [LinkToken=4 bytes] [FUNC/LEN=0] [Key=empty]`.
4. Assign each newly-linked Cookie a 4-byte AP-side address for
   subsequent unicast traffic.
5. Log everything the Cookie sends after linking — the sensor uploads
   should surface here.

Reference implementations available in-repo:

- `simpliciti/simpliciti-1.2.0-mspgcc/Projects/Applications/` — TI's
  own AP code, and `Components/nwk_applications/nwk_join.c` for the
  Join handler.
- `prior-art/iSmartAlarm/scripts/ism_rx.py` — Seekintoo's GNU Radio +
  Python 2 SimpliciTI RX with PN9 dewhitening and Join spoofing on a
  CC1110-based device. Adjacent-protocol reference, not drop-in.

Fallback if step 3 stalls on any ambiguity: put the real Mother next
to an SDR (it happily re-init's SimpliciTI without cloud) and capture
a live Mother↔Cookie handshake to see exactly what layout sen.se picked.

### 📡 Bridging to Home Assistant

**Recommended deployment:** ESP32 + CC1101 firmware that does the
SimpliciTI AP role and re-emits the sensor readings as
[BTHome](https://bthome.io) BLE advertisements — HA auto-discovers
BTHome sensors natively, no MQTT broker or Wi-Fi credentials required.

```
CC1101 RX  →  Cookie SimpliciTI Join reply + PLL rx  →  parse
temp/accel  →  BTHome BLE advertisement  →  HA auto-discovery
```

USB-powered wall unit next to the bed. Nothing about SimpliciTI-to-HA
benefits from being battery-powered.

Libraries: `BTHomeV2` (BLE broadcast), `SmartRC-CC1101-Driver-Lib`
(CC1101 SPI), plus the vendored `simpliciti-1.2.0-mspgcc/Components/`
network layer.

An [rtl_433 upstream `simpliciti.c` device decoder](https://github.com/merbanan/rtl_433)
would benefit more than this project (TI Chronos watch and other
sub-GHz networks use SimpliciTI too) — the constants are all well
defined here.

### CC1101 hardware options

Fully assembled ESP32 + CC1101 boards, cheapest first:

| option | price | notes |
|---|---|---|
| [Evil Crow RF](https://github.com/joelsernamoreno/EvilCrow-RF) | ~$27 | Two CC1101 radios + ESP32 (one radio is overkill). Bare board. |
| [M5Stack Basic](https://shop.m5stack.com/products/esp32-basic-core-iot-development-kit-v2-7) + [M5Stack CC1101 Module](https://shop.m5stack.com/products/m5stack-cc1101-module-855-925mhz) | ~$43 | Stacked, no wiring. CC1101 855–925 MHz w/ SMA. ESP32, LCD, USB-C. |
| [M5Stack CoreS3](https://shop.m5stack.com/products/m5stack-cores3-esp32s3-lotdevelopment-kit) + [M5Stack CC1101 Module](https://shop.m5stack.com/products/m5stack-cc1101-module-855-925mhz) | ~$61 | ESP32-S3 + BLE 5 (cleaner BTHome side), touch display. |
| [LilyGO T-Embed CC1101](https://www.lilygo.cc/products/t-embed-cc1101) | ~$50 | 1.9" TFT + battery. Well-supported by [`dbuezas/esphome-cc1101`](https://github.com/dbuezas/esphome-cc1101). Smoothest software path. |

Flipper Zero has a CC1101 but stock and community firmwares
(Momentum/Xtreme/Unleashed) do not decode SimpliciTI; a custom `.fap`
app is a few-weekends project. Useful for RSSI hunting and archival
`.sub` captures, not as an AP.

## 🕰️ FCC context

Original hardware filings:

| FCC ID | Product | Date | URL |
|---|---|---|---|
| 2ABGNCOO001 | Cookie (COO001) | 2014-03-31 | https://fcc.report/FCC-ID/2ABGNCOO001/ |
| 2ABGNMOM001 | Mother (MOM001) | 2014-03-31 | https://fcc.report/FCC-ID/2ABGNMOM001/ |
| 2ABGNPEA001 | ThermoPeanut (PEA001) — BLE, dead end | 2016-06-21 | https://fcc.report/FCC-ID/2ABGNPEA001/ |

ThermoPeanut is BLE (2.4 GHz), but sen.se put a per-device auth key on
the server side. With the cloud dead, the handshake can't complete —
the device pairs but no decoded payload is accessible. Not a shortcut.

EU units use 868 MHz (CE/ETSI filings, not FCC). Confirm region before
tuning a receiver.

The `Cookies are all the same hardware` claim was validated by the
user manual (page 1) — one SKU, cloud-side interpretation:

> "So many skills in just one tiny sensor. Motion Cookies are
> seamlessly reprogrammed according to what you want to use them for."

Every Cookie has the same accelerometer + temperature + battery
payload; sen.se's "apps" were 100 % cloud-side. Buy any Cookie on eBay
— they don't need to be labeled "temperature."

## ❓ Open questions

- **SimpliciTI address byte order** (little vs big endian). Spec §4.8
  says multi-byte numbers are little-endian, so `1f a8 25 25` on the
  air might be numeric `0x2525a81f`. Only matters if cross-referencing
  against a printed ID.
- **Port-7 (PLL) 3-byte payload semantics.** Two bytes look like a
  slowly-varying counter; the third might be parity/status. Not in the
  SimpliciTI spec — TI didn't publish a table for this reserved port.
  sen.se probably added it as their own heartbeat.
- **EU 868 MHz frame layout.** Assumed identical (same CC430F5137 +
  same SimpliciTI stack, band-shifted) but not verified.

## 🔗 References

- FCC Part 15.249 limits: <https://www.ecfr.gov/current/title-47/section-15.249>
- TI CC1101 datasheet: <https://www.ti.com/product/CC1101>
- rtl_433: <https://github.com/merbanan/rtl_433>
- URH (Universal Radio Hacker): <https://github.com/jopohl/urh>
- dbuezas/esphome-cc1101 ESPHome external_component: <https://github.com/dbuezas/esphome-cc1101>
- rtl_433_ESP (ESP32 port): <https://github.com/NorthernMan54/rtl_433_ESP>
- OpenMQTTGateway: <https://docs.openmqttgateway.com/>
- BTHome: <https://bthome.io>
- ccarlo64/freemother (cloud emulator, sleep Cookie only): <https://github.com/ccarlo64/freemother>

Prior SimpliciTI RE work referenced in `prior-art/iSmartAlarm/`:

- Seekintoo / Dayton Pidhirney, "DIY Smart Home Security? Meh..
  (March 2017) — attacked iSmartAlarm (CC1110 + SimpliciTI). Found the
  ASCII string `"SimpliciTI's Key"` in that firmware (iSmartAlarm used
  TI's default XTEA key), built a GNU Radio + PN9 + XTEA + spoof
  pipeline. sen.se's Cookies don't XTEA-encrypt, so only the RX +
  dewhitening + Join-spoof pieces apply here.
  Blog: <https://blog.seekintoo.com/diy-smart-home-security-meh.html>
  Code: <https://github.com/seekintoo/iSmartAlarm>
- rtl-sdr.com writeup: <https://www.rtl-sdr.com/identifying-issues-that-can-be-used-to-disable-iot-alarms/>
