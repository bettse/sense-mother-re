# Cookie board — chip inventory

PCB rev: `v2.9b` (silk on top side).

## Main MCU

**TI CC430F5137** — MSP430 + CC1101 radio, one 48-QFN. Confirmed from
close-up: chip markings `CC430 / F5137 / TI 36K E / A32Y G4`
(see `cc430-marking-*.jpg`). Datasheet vendored at
`prior-art/datasheets/cc430f5137.pdf`.

This is what runs the whole SimpliciTI + sensor app. Dumping its
internal flash via SBW (Spy-Bi-Wire on TEST + RST pins) is the
highest-leverage next step for finishing the protocol RE.

## Peripheral chips

Three small ICs sit along the top edge of the PCB between the CC430
and the meandered PCB antenna.

### Chip A — likely accelerometer

Photo: `chip-accel-marking-HE3.jpg`.

Markings (best read; the surface is very rough at this magnification):
- top: `328`
- middle: `HE3`
- bottom: `08 ID` (or `08 IB`)

Working hypothesis: **Bosch Sensortec accelerometer**, likely a
BMA-series digital 3-axis part. Bosch parts of that era use 3-char
codes on line 2 with lot/date on other lines. Could not confirm the
specific part number from marking databases — the top line is likely
a date code (2003+28 → week 28 of 2003? unlikely — more probably a
production run marker).

Alternative interpretations: could also be a Fairchild / ON
Semiconductor / Diodes Inc SOT-23-5/6 opamp or reference. Without
better lighting/magnification, undecidable.

### Chip B — likely LDO / power management

Photo: `chip-ldo-marking-0175-M.jpg`.

Markings:
- top: `0175 (M-in-circle logo)`
- bottom: `9316AD` (lot code)

Working hypothesis: **Micrel** (M-in-circle is Micrel's pre-Microchip
logo). Likely a low-Iq LDO like MIC5205, MIC5219, or MIC5225 —
these are common in CR2016-powered sensor nodes because their
quiescent current is ≲ 1 µA. The `0175` doesn't directly match any
Micrel part I recognize, so this is a marking-family guess rather
than a firm ID.

Alternative: some Maxim / Motorola-lineage parts also use a
circle-M — could be a MAX8880-family LDO.

### Chip C — likely temperature sensor OR a second support IC

The third package (visible in `pcb-top-closeup.jpg` between the CC430
and the battery contact) — no dedicated close-up yet.

Working hypothesis: either a discrete temperature sensor (TI TMP102 /
Analog Devices ADT7420 / Maxim DS7505) reached over I²C, OR the
temp measurement is done by the CC430 itself using its internal ADC
plus an external thermistor — in which case this chip is something
else (maybe an EEPROM / boot-time storage for calibration constants,
or a battery-voltage monitor).

A close-up on this chip's markings would nail it.

## Passives + other marked components

- `C6`, `C21`, `C27` — capacitors (values not visible)
- `D1` — diode marker; near the battery corner. Could be reverse-
  polarity protection or an ESD suppressor. If it's actually the
  temperature-sensing element, that'd be a thermistor labeled as a
  diode-family footprint.

## Battery

CR2016 coin cell, 3.0 V nominal. Contact clip visible in
`enclosure-open.jpg` on the left edge of the PCB (as oriented in
that photo).

## PCB antenna

Meandered trace on the right side of the PCB (in the enclosure-open
photo) — 915 MHz quarter-wave meander, tuned by the trace length +
the surrounding ground plane clearance. Not a discrete antenna.
