# sen.se on-air observations — Mother-powered captures

Captured on 2026-07-04 with the RTL-SDR near the Mother, one real
`sen.se Mother` powered on and safe song / awesome you Cookies in
various link states. Everything below is from
`captures/mother-cycles/*.json` and the live monitor stream.

## Message inventory

The Mother's SimpliciTI stack broadcasts on multiple ports with what
looks like a small pool of SRCADDRs — all one byte apart:

| Port | Sender bits | Fwd | Payload len | Who sends | Frequency |
|---|---|---|---|---|---|
| 1 | `res` (11) | 1 | 1 byte | Mother (`6fec1614`, `508d4114`, `6fed4114`) | ~30 s |
| 3 | `ED` (00) | 0 | 9 bytes (`XX 01 TID 08 07 06 05 02 02`) | Cookie standard Join | ~20-40 s while unlinked |
| 3 | `ED` (00) | 0 | 9 bytes (`XX 01 TID 08 07 YY YY 72 ZZ`) | Cookie **special / linked** Join | ~90 s post-link |
| 7 | `ED` (00) | 0 | 1 byte | Cookie PLL heartbeat / counter | ~15 s |
| 9 | `res` (11) | 1 | 9 bytes | Mother broadcast | ~1 min |
| 13 | `RE` (01) | 1 | 1 byte | Mother unicast to Cookie (only one seen) | rare |
| 29 | `RE` (01) | 1 | 9 bytes | Mother broadcast | ~1-2 min |

Notes:

- **All Mother-side frames have `fwd=1`** (forwarded bit set). Cookie
  frames have `fwd=0`.
- **Mother's SRCADDR is not fixed.** Same physical Mother emits with
  different last-byte SRCADDRs by port (`6fec1614` on port 1,
  `6fec1514` on port 9, `6fec1615`(!) on some sniff). The `6fec1615`
  case is almost certainly rtl_433 flipping the last-byte LSB — that
  address collides with safe song's real Cookie address. Anything
  attributed to Cookie SRCADDR *with `fwd=1` and `sender=res`* should
  probably be treated as a Mother frame with a corrupt SRCADDR.
- The addresses `6fec16XX` (0x14/0x15/0x17), `508d41XX`, `6fed41XX`,
  `1c1b596e`, `2e4fef17` all showed up as Mother-side (`fwd=1`) during
  a period when only ONE physical sen.se Mother was on. Sen.se is a
  defunct single-vendor network — there's no other Mother anywhere
  near here. Reading these as "different networks" is wrong.

## 9-byte payload shape

The port-9 / port-29 broadcasts and the port-3 special-form Cookie
frames all carry 9-byte payloads that look like:

```
byte 0    byte 1..3       byte 4..8
[nonce]   [3 bytes ??]    [5-byte device-specific tail]
```

Same-tail examples (same physical Mother, different broadcasts):

```
508d4114 port 9: 83 93 25   e9 10 f0 8d 72 6c
6fec1514 port 9: 31 92 27   e9 10 f0 8d 72 6c   (same tail from same Mother)
6fed4117 port 29: 7c b7 02  2b 3f 1d 9d 92 b3   (different tail — different Cookie index?)
1c1b596e port 9: 9b 93 5d   eb 3f 1d 9d 92 b0
```

The trailing 5 bytes look like a **LinkToken assigned by the Mother
to a specific Cookie** — different Cookies get different tails, same
Cookie's traffic (from the same Mother) shares the tail. Awesome you's
linked-form Cookie port-3 payload trailed in `70 8d 72 6c` — matching
the port-9 Mother-broadcast tail for the same Cookie. So the tail =
per-Cookie link identifier stamped by the Mother.

Bytes 1-3 are the interesting slot — small enough to be one-byte
sensor reads (temperature / accel / battery voltage). Byte 0 tracks
the port-7 counter, so it's a nonce.

## The Cookie counter

The port-7 payload byte is a **plain monotonic counter** that Cookie
sends on every ~15 s beacon and increments through port-3 sends as
well. Not sensor data.

When Cookie fires a port-3 broadcast, its "nonce" (byte 0 of the
payload) picks a value; the following port-7 beacon then continues at
`nonce + 1`. That's what produces the big apparent "jumps" in the port-7
counter (e.g. `96 → e1 → 6c → 76` in one capture) — each jump
corresponds to a port-3 send whose nonce we did or didn't observe.

## What we did NOT see

- **No unicast Cookie → Mother traffic** on any app port in ~30 min of
  captures across ports 4-30.
- **No sensor data unambiguously attributable to a Cookie.** The
  9-byte broadcasts that briefly looked Cookie-originated were on
  addresses one bit away from Cookie SRCADDRs and are more consistent
  with Mother broadcasts + a rtl_433 flex-decode bit slip in SRCADDR.
- **No Cookie response to Mother-side broadcasts.** Cookies just do
  their beacon + Join broadcasts; the port-9 broadcasts happen with
  or without Cookies present.

## Implication for our AP

To harvest sensor data, our AP needs to be the Cookie's link target.
Then the Cookie will unicast us its sensor payload on some app port
(seen once at port 13 as a Mother → Cookie unicast).

Passive sniffing of a Cookie-linked-to-real-Mother session is unlikely
to give us the sensor byte layout — sensor data flows out of the RF
domain as unicast to the AP.

The Flipper AP already gets Cookies to Join (proved earlier). What's
left is (a) keep the app running long enough to catch a post-link
unicast from a joined Cookie, (b) respond to any port-6 polls to keep
the link healthy.
