# CC430F5137 SBW pinout — where to solder on the Cookie

Goal: get **TEST**, **RST**, **VCC**, and **GND** wired to a TI Launchpad
(or any SBW-capable MSP430 debugger), so we can attempt to dump the
Cookie's internal flash and read sen.se's application-layer protocol
on top of SimpliciTI.

**Big unknown**: whether the CC430's JTAG-lock fuse is blown. If it is,
this whole path is dead and no amount of soldering matters. If it's
not, this is a couple hours of work end-to-end.

## Datasheet pin numbers (CC430F5137 RGZ 48-QFN)

Per `prior-art/datasheets/cc430f5137.pdf` Fig 4-3 / Table 4-2:

| Pin | Function                       | For SBW? |
|----:|--------------------------------|:-:|
| 39  | TEST / SBWTCK                  | ✅ signal |
| 40  | RST/NMI / SBWTDIO              | ✅ signal |
| 41  | DVCC (digital supply)          | ✅ can be tapped for VCC |
| 42  | AVSS (analog ground)           | ✅ can be tapped for GND |
| 45  | AVCC (analog supply)           | alternate VCC point |
| 8   | DVCC                           | alternate VCC point |
| 29  | RF_P → PCB antenna             | not for SBW |
| 30  | RF_N                           | not for SBW |
| die pad | exposed thermal pad = GND  | easiest GND point if reachable |

Convenience win: **TEST (39), RST (40), DVCC (41), AVSS (42) are FOUR
adjacent pins** on one edge of the QFN. Solder to those four and you
have every signal you need in one contiguous run.

## Pin 1 orientation on this specific board

Pin 1 is TI's standard "dot" indicator, at the top-left corner of the
package when the chip marking reads left-to-right in normal orientation
(`CC430` top row, `A32Y G4` bottom row). Pin numbering goes
**counter-clockwise** from pin 1.

On our Cookie photos the chip is rotated 90° from that reading
orientation — the marking runs **top-to-bottom** with `CC430` at the
top of the photo and `A32Y G4` at the bottom.

That means, in the photo orientation used by
`cc430-marking-1.jpg` / `cc430-marking-3.jpg`:

```
        Right side of photo  ← pins 37-48 of QFN (top edge in std)
      ↓
    +-------------+----+
    |             |    |  ← Pin 1 dot is HERE
    |   C C 4 3 0 |    |    (top-right corner of chip in the photo)
    |   F 5 1 3 7 |    |
    |   T I  36K E|    |
    |   A 3 2 Y G4|    |
    |             |    |
    +-------------+----+
      ↑                  ↑
   Bottom edge in photo  Left edge in photo
   = pins 13-24          = pins 1-12
   (bottom of QFN std)   (left edge of QFN std)

   Right edge of photo   Top of photo
   = pins 25-36          = pins 37-48 (going right → left)
   (right edge std)      → PIN 39 = 3rd from pin-1 corner
                         → PIN 40 = 4th from pin-1 corner
                         → PIN 41 = 5th from pin-1 corner
                         → PIN 42 = 6th from pin-1 corner
```

So in that photo the four SBW pins are along **the top edge of the
chip in the photo, close to the top-right corner** — 3rd through 6th
pins in from the pin-1-dot corner.

## Physical soldering plan

CC430F5137 RGZ package is 7 mm × 7 mm QFN with 0.5 mm pin pitch. The
pads are ~0.25 × 0.6 mm each and stick out only under the QFN — no
side leads. To wire to them you basically have three options:

1. **Land wires directly on the pin fillets** at the edge of the QFN
   — feasible under a scope with 32-38 AWG magnet wire and a fine-tip
   iron. Toughest option; risk of pin bridges.
2. **Trace back to a via or component pad** the four SBW-adjacent
   pins connect to. Vias are easier to solder to than QFN pin fillets.
   Requires tracing on the PCB with a microscope — worth doing before
   attempting (1).
3. **Test points**. Some designs put SBW test points on the bottom of
   the board for programming during manufacture — check
   `pcb-bottom.jpg`. If sen.se left any 1-mm pads with silk labels
   like `TST`, `RST`, they're the ICSP test points and directly wire
   to pins 39/40.

**Look for option 3 first** — it makes the rest trivial.

## Pull-ups / decouplers to keep in mind

- Pin 40 (RST) usually has a 47 kΩ pull-up to VCC and 2.2 nF cap to
  ground on the board. The pull-up stays connected during SBW — fine.
  The cap is a problem if > 2.2 nF (SBW upper limit); keep it in mind
  if the connection is flaky.
- Pin 39 (TEST) sometimes has a small pull-down; usually harmless.
- DVCC (41): if the board is running on CR2016, the Launchpad should
  drive its target VCC to 3.0 V, matching. Alternatively, remove the
  battery and let the Launchpad power the whole board.

## Launchpad pin-out for SBW

Any MSP430 Launchpad with the eZ-FET debugger (MSP-EXP430G2, MSP-EXP430FR2xx,
MSP-EXP430FR5xx, etc.) can dump a CC430F5137 via SBW. Wiring:

| Launchpad pin | Cookie CC430 pin |
|---|---|
| SBWTCK (usually J3 pin near reset) | 39 (TEST) |
| SBWTDIO / RST | 40 (RST) |
| VCC (3.3 V from Launchpad, jumper-selectable) | 41 (DVCC) or 45 (AVCC) |
| GND | 42 (AVSS) or die pad |

Then `mspdebug tilib` or TI's UniFlash can attempt an ID + full-flash
dump.

## What "fuse blown" will look like

- UniFlash / mspdebug reports "Device ID mismatch" or "Security fuse
  blown" on connect.
- Sometimes just says "Target not responding" — that's ambiguous
  (could be wiring, could be fuse). Try re-seating everything twice
  before concluding.

If we get past the ID check, `mspdebug tilib "prog file.hex"` or
`mspdebug tilib "save_raw 0x0000 0x10000 flash.bin"` for a full
0-64 KiB dump.
