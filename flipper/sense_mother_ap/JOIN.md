# SimpliciTI Join Protocol — sen.se Cookie ↔ Mother

Reference for building an Access Point that can link sen.se Cookies to
extract sensor data (temperature, accelerometer). All frame layouts
and offsets below come from the vendored TI SimpliciTI 1.2.0 reference
(`simpliciti/simpliciti-1.2.0-mspgcc/Components/simpliciti/`); sen.se
did not modify the network layer.

## Frame envelope (recap)

After preamble + sync `0xD391` + PN9 dewhitening:

```
LENGTH | DSTADDR(4) | SRCADDR(4) | PORT | DEVINFO | app_payload | FCS(2)
```

- `LENGTH` = count of bytes AFTER length byte, EXCLUDING the 2-byte CRC.
- `PORT` bit 7 = forwarded, bit 6 = encrypted, bits 5:0 = port number.
- `DEVINFO` bit 7 = ACK_REQ, bit 6 = SLEEP, bits 5:4 = sender type
  (0 = End Device, 1 = Range Extender, 2 = Access Point), bit 3 = ACK_REP,
  bits 2:0 = hop count.

## Port assignments

| Port | Name | Direction | Purpose |
|------|------|-----------|---------|
| 3 | `SMPL_PORT_JOIN` | ED ↔ AP | Join request / reply |
| 6 | `SMPL_PORT_MGMT` | ED → AP | Poll AP for queued frames |
| 7 | `SMPL_PORT_PLL` | ED → any | Beacon (sen.se-specific, ~15 s) |
| 4-30 | app ports | ED ↔ ED / ED ↔ AP | Application data |

TI's stock ports 1-2 are link-service; port 5 is frequency-agility. Sen.se
almost certainly reused port 4 or 8 for sensor payloads — TBC on-air.

---

## Step 1: Cookie broadcasts Join request (port 3, we already RX this)

Every ~1 minute the Cookie sends this on `dstaddr=FF FF FF FF`.

Application payload — 8 bytes (`nwk_join.c:76`, `nwk_join.h:52-57`):

| Off | Field | Bytes | Value |
|-----|-------|-------|-------|
| 0 | `REQ_JOIN` | 1 | `0x01` |
| 1 | Cookie TID | 1 | increments per attempt |
| 2 | Join Token | 4 | **`08 07 06 05`** — sen.se's shared secret |
| 6 | NumConn | 1 | non-zero = "I can also handle ED frames" |
| 7 | ProtocolVersion | 1 | matches TI's `nwk_getProtocolVersion()` |

Legacy Cookies (pre-SimpliciTI 1.0.6) send a 7-byte payload omitting
ProtocolVersion. TI's `nwk_join.c:225` only enforces version match when
the payload is longer than the legacy size.

## Step 2: AP replies unicast (port 3, THIS IS PHASE 2)

Send within Cookie's RX window (a few ms per `NWK_REPLY_DELAY` in the
Cookie's join code). Layout — 7 bytes (`nwk_join.c:249-259`, `nwk_join.h:59-62`):

| Off | Field | Bytes | Value |
|-----|-------|-------|-------|
| 0 | `REQ_JOIN \| REPLY_BIT` | 1 | `0x81` |
| 1 | echo Cookie TID | 1 | copy from request |
| 2 | Link Token | 4 | our choice — Cookie stores as-is |
| 6 | CryptKeySize | 1 | **`0x00`** — sen.se uses no encryption |
| 7… | CryptKey | 0 | omit |

**DSTADDR** = the Cookie's SRCADDR from the request.
**SRCADDR** = our chosen AP address.
**PORT** = `0x03` (no forwarded/encrypted flags set).
**DEVINFO** = `0x20` (sender type = Access Point, hop = 0). ACK_REQ = 0 —
Join replies don't request ACK; the Cookie signals success by ceasing
to broadcast Join and switching to normal ED behavior.

Full on-air frame (before whitening + FCS):

```
LEN=0x12 | DST=<cookie SRC> | SRC=<AP addr> | 0x03 | 0x20 |
  0x81 | tid | LinkToken(4) | 0x00
```

`LEN = 4+4+1+1+7 = 17 = 0x11`. Add 2 for CRC → 19 bytes on the wire after
the length byte.

## Step 3: What the Cookie does next (Phase 3, TBC)

TI's `nwk_join.c` distinguishes two Cookie behaviors based on the RX
type field it advertised in the Join request:

- **Always-On ED** (mains-powered — not our case for battery Cookies) —
  Cookie can send/receive anytime after Join.
- **Sleeper / Polling ED** (`F_RX_TYPE_POLLS`, `nwk_join.c:284`) — Cookie
  wakes periodically, polls the AP for held frames, sends its own, sleeps.

CR2016-powered Cookies must be sleepers. So after Join we expect one of:

a. **Cookie polls us** — periodic `SMPL_PORT_MGMT` (port 6) requests:
   ```
   0x01 | TID | PollPort | PollAddr(4)   ← 7 bytes
   ```
   We reply with any queued frame for `(PollPort, PollAddr)`. If there
   is nothing queued, AP is silent. See `nwk_mgmt.c:222` `send_poll_reply`.

b. **Cookie sends sensor data unsolicited** — after Join, some subset of
   port-7 beacons might start carrying real payloads, or a new port
   (4? 8?) may appear from this SRCADDR.

Whichever happens, the app-layer payload format (temperature encoding,
accel encoding, battery voltage, etc.) is **sen.se-proprietary**. It
lives inside the port-N payload, not in SimpliciTI framing.

**Empirical discovery plan:**

1. Log every frame from the joined Cookie's SRCADDR, on every port,
   for at least 5 minutes after Join.
2. If we see port 6 polls, we must reply — even empty replies keep the
   Cookie's TID window ticking — otherwise it may re-Join.
3. Correlate on-air payloads to real-world stimuli: palm-warm the Cookie
   and watch which byte(s) change; flip it and watch accel bytes.

## Choosing our AP address

The address just needs to be unique per Cookie's peer list and to not
collide with real observed neighbor APs (from the README: `50 8d 41 14`,
`b0 1b 59 6e`, `b0 05 27 74`, `4f 16 f1 54`). We use **`DE AD BE EF`** —
easy to eyeball in captures, and no chance a real Mother picked it.

## Choosing the Link Token

Arbitrary — TI's reference uses `0xDEADBEEF` literally. Cookie treats
it as an opaque 4-byte value stored alongside the peer address. It only
matters if we later run multiple APs and want frames scoped to one AP;
for our one-AP setup any value works.

## References in-repo

- `simpliciti/simpliciti-1.2.0-mspgcc/Components/simpliciti/nwk_applications/nwk_join.{c,h}` — canonical Join implementation
- `simpliciti/simpliciti-1.2.0-mspgcc/Components/simpliciti/nwk_applications/nwk_mgmt.{c,h}` — poll / store-and-forward
- `simpliciti/simpliciti-1.2.0-mspgcc/Documents/SimpliciTI Specification.pdf` §5, Tables 15-16 — spec-level frame layouts
- `prior-art/iSmartAlarm/scripts/ism_rx.py` — Seekintoo's Join-spoof reference (adjacent, XTEA-encrypted variant)
