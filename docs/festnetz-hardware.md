# Landline variant: hardware

*English · [Deutsch](festnetz-hardware.de.md)*

Compared with the hybrid device, **modem, SIM and GPS** are dropped. New are the
**cradle with speaker** and the **spring contacts**. Keys, emergency button with
cover, amplifier, earpiece, microphone and battery gauge stay the same, as does the
software layer for them (`hardware.py`, `audio.py`).

Prices are **rough estimates** (as of late 2026, single unit, incl. VAT, without
shipping). I only checked the Pi and the modem against dealer listings [1, 2].

## Handset parts list

| # | Part | Purpose | approx. € |
|---|---|---|---|
| 1 | Raspberry Pi Zero 2 W (without header) | computer, **Wi-Fi 2.4 GHz** | 18–24 [1] |
| 2 | microSD 32 GB “High Endurance” | system (read-only, overlay FS) | 10 |
| 3 | USB sound card CM108 (board without case) | audio in/out | 6–8 |
| 4 | TPA2016D2 amplifier breakout | L = earpiece, R = speaker, AGC/limiter | 10 |
| 5 | Earpiece 32 Ω, speaker 28 mm 8 Ω | call at the ear, ringing in the handset | 5 |
| 6 | Electret or MEMS microphone | talking, voice dialing, dictation | 3 |
| 7 | MCP23017 breakout | 16 keys via I²C | 4 |
| 8 | 16 Cherry MX format switches + printed caps | keypad (`cad/omafon_tasten.scad`) | 10 |
| 9 | Emergency button + microswitch for the cover | SOS directly on GPIO (not via I²C) | 5 |
| 10 | 2 volume switches | directly on GPIO | 1 |
| 11 | LiPo 1S **3000 mAh** with protection circuit | battery (rationale below) | 12–15 |
| 12 | Charge/path controller with bq24074 (PGOOD output) | charging from the cradle, charge detection | 10–15 |
| 13 | Boost converter 3.7 → 5 V, **1 A** is enough | Pi supply (previously 2–3 A because of the modem) | 6–8 |
| 14 | MAX17048 breakout | battery level in percent | 6 |
| 15 | Vibration motor, bright LED | feel the ringing, message indicator | 3 |
| 16 | **Signal relay 2× changeover, 5 V** (e.g. TQ2/G6K type) + flyback diode | switch the speaker to the cradle automatically | 3 |
| 17 | Contact plate: 5 brass discs Ø5 mm, 2 steel discs | counterpart to the spring contacts (`handteil_kontakte`) | 3 |
| | **Handset total** | | **approx. 120–145** |

## Cradle parts list

| # | Part | Purpose | approx. € |
|---|---|---|---|
| 1 | 5 spring contacts (pogo pins) Ø2 mm, travel ≥ 1 mm | +5 V, 2× GND, SPK+, SPK− | 4 |
| 2 | 2 magnets 8 × 3 mm (neodymium) | the phone snaps in noticeably | 2 |
| 3 | Full-range speaker 50 mm, 8 Ω, ≥ 3 W | ringing and hands-free in the cradle | 6–10 |
| 4 | USB-C socket board (with 5.1 kΩ CC resistors) | power input | 2 |
| 5 | USB-C power supply 5 V / 3 A | supply | 10 |
| 6 | Steel discs approx. 150–250 g, 4 rubber feet, 2 M3 screws | stability, non-slip | 4 |
| 7 | PETG approx. 150 g | `cad/omafon_ladeschale.scad` | 4 |
| | **Cradle total** | | **approx. 30–35** |

**Total approx. €150–180.** Compared with mobile, these are dropped: SIM7600E-H HAT
(approx. €90–100 [2]), LTE and GNSS antennas (approx. €10), SIM contract.

## Power budget and battery

| State | Power (estimated) | Source/assumption |
|---|---|---|
| Pi Zero 2 W idle, Wi-Fi connected | approx. 0.60 W | 120 mA at 5 V, Wi-Fi +11 mA [3] |
| Pi optimized (HDMI, Bluetooth, camera detection off) | approx. 0.46–0.50 W | 92.7 mA [3] |
| Amplifier off, MCP23017, MAX17048, LED blinking | approx. 0.03 W | datasheet values, rough |
| Call (Wi-Fi active, audio, baresip) | approx. 1.2–1.5 W | assumption, measure on the device |
| *for comparison: SIM7600 idle* | *approx. 0.1 W*, transmit peaks up to 2 A | hybrid device |

Calculation for 3000 mAh: 3.7 V × 3.0 Ah = 11.1 Wh; after the converters (approx. 85 %)
about 9.4 Wh.
- Standby: 9.4 Wh ÷ 0.63 W ≈ **15 h**, optimized ÷ 0.5 W ≈ **19 h**
- Talk time: 9.4 Wh ÷ 1.35 W ≈ **7 h**

**Conclusion:** the phone belongs in the cradle at night and mostly during the day too.
Lifting answers, putting it down hangs up – that fits. A **smaller battery**
(e.g. 1500 mAh, about 7–9 h standby) would work technically because there are no more
2 A peaks. For a person who sometimes leaves the phone lying in the armchair, I don’t
recommend it, though. The battery warnings at 20/10/5 % are still spoken.

## Wi-Fi antenna

- The Pi Zero 2 W has **only a PCB antenna** and no antenna connector. A U.FL
  modification is possible but voids the radio approval [4]. **Don’t do it.**
- Mount the board so that the antenna (narrow side next to the mini HDMI) sits **at the
  top of the housing**, not covered by the battery. No metal foil, no screws and no
  traces of other boards within about 10 mm.
- Check reception: the info key says „Verbindung zur Fritzbox gut/mittel/schwach“
  (“connection to the Fritzbox good/medium/weak”; thresholds −67 / −75 dBm). If it is
  “weak” at grandma’s favorite spot: a Fritz!Repeater in the mesh. Don’t modify the
  phone.
- 2.4 GHz only. Leave the 2.4 GHz band on in the Fritz!Box.

## Wiring

### GPIO and I²C (as for mobile, except the modem)

| Signal | Pi pin (BCM) | Note |
|---|---|---|
| I²C SDA/SCL | 2 / 3 | MCP23017 0x20, TPA2016 0x58, MAX17048 0x36 |
| SOS button | 22 | direct, **not via I²C** (the emergency call also works if I²C fails) |
| SOS cover (microswitch) | 23 | inverted |
| Volume up / down | 24 / 25 | |
| **In the cradle** (bq24074 PGOOD) | 27 | low = power from the cradle = “docked” |
| Vibration (PWM) | 12 | via transistor |
| LED | 13 | via series resistor/transistor |
| ~~Modem PWRKEY~~ | ~~6~~ | **unused** |
| Sound card | USB (via test pads or OTG adapter) | |

### Power and contacts

```
 Cradle                                         Handset
 ──────                                         ───────
 USB-C 5V ─┬─────────── Pogo 1 (+5V) ─── Pad 1 ─┬─> bq24074 IN ── battery 1S
           │                                    │       │ PGOOD ──> GPIO27
           │                                    │       └─ SYS ──> converter 5V/1A ──> Pi 5V
           │                                    └─> relay coil ─┐ (flyback diode)
 GND ──────┴─────────── Pogo 2+3 (GND) ── Pad 2+3 ─────────────┘
                                                        TPA2016 channel R (BTL)
 Speaker 50 mm ──────── Pogo 4 (SPK+) ─── Pad 4 ── relay NO ─┐ ┌─ NC ── speaker 28 mm
                    └── Pogo 5 (SPK−) ─── Pad 5 ── relay NO ─┘ └─ NC ── (in the handset)
```

- The **relay switches without software**. When the cradle voltage is present, the
  speaker channel goes to the cradle, otherwise to the small speaker in the handset.
  If the software hangs, it still rings where the phone is.
- The coil hangs on the cradle voltage, so it doesn’t load the battery.
- The software knows via PGOOD (GPIO 27) that the phone is docked. With
  `dock_speaker: true` it puts calls in the cradle on the speaker channel.
- The TPA2016 is a class D amplifier with a bridged output. **No output may go to GND**,
  hence the two-pole relay. Keep speaker wires short; ferrite if there is interference.
- Two GND contacts: lower contact resistance while charging (up to approx. 1 A).
- Contact order 1–5 from the left (seen from the front). The contact carrier has a mark
  at contact 1. The coding rib prevents inserting it the wrong way.

### Operation at the cradle (software, `config.festnetz.example.yaml`)

| Setting | Effect |
|---|---|
| `answer_on_lift: true` | if it rings and grandma takes the phone out of the cradle, she is connected |
| `dock_in_call: hangup` | putting it back ends the call (like a classic handset) |
| `dock_in_call: handsfree` | putting it back switches to hands-free via the cradle |
| `dock_speaker: true` | answering with the key in the cradle = hands-free via the cradle |

## Sources

1. Notebookcheck (BerryBase/Welectron prices Pi Zero 2 W) – https://www.notebookcheck.com/Deal-Raspberry-Pi-Zero-2-W-fuer-faire-24-Euro-sofort-verfuegbar.735276.0.html , https://www.notebookcheck.com/Deal-Raspberry-Pi-Zero-2-W-zum-vernuenftigen-Preis-sofort-verfuegbar.605703.0.html
2. buyzero.de / eBay (SIM7600G-H HAT €90–100; E-H price in € not found) – https://buyzero.de/products/waveshare-19485-sim7600g-h-4g-hat-b
3. CNX Software: Raspberry Pi Zero 2 W power consumption – https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/
4. Brian Dorey: Zero 2 W external antenna mod; Tom's Hardware on it – https://www.briandorey.com/post/raspberry-pi-zero-2-w-external-antenna-mod , https://tomshardware.com/news/raspberry-pi-zero-2-w-external-antenna-mod
