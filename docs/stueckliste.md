# Bill of materials

*English · [Deutsch](stueckliste.de.md)*

For both variants: **landline** (Fritz!Box via Wi-Fi, `backend: sip`) and
**hybrid** (additional LTE modem for on the go, `backend: hybrid`). The columns
“L” and “H” give the quantity per variant.

Prices are **estimates** for single units including VAT, without shipping (as of
late 2026). Only the Pi and the modem HAT were checked against dealer listings, see
[festnetz-hardware.md](festnetz-hardware.md#sources). Connections:
[verkabelung.md](verkabelung.md). Printed parts and assembly:
[druckteile.md](druckteile.md).

## Electronics

| Part | L | H | approx. € | Note |
|---|---|---|---|---|
| Raspberry Pi Zero 2 W (without header) | 1 | 1 | 18–24 | 2.4 GHz Wi-Fi only; don't modify the PCB antenna |
| Pin header 2 × 20 (2.54 mm) | – | 1 | 1 | for the HAT; landline: solder the wires directly |
| microSD 32 GB “High Endurance” | 1 | 1 | 10 | the system runs with an overlay file system |
| USB sound card CM108 (board without case) | 1 | 1 | 6–8 | the card supplies the microphone bias |
| Micro-USB OTG adapter or short wires to the USB test pads | 1 | 1 | 2 | see wiring |
| MCP23017 breakout (I²C, 16 inputs) | 1 | 1 | 4 | address 0x20 |
| TPA2016D2 breakout (2 × class D, AGC) | 1 | 1 | 10 | L = earpiece, R = speaker |
| MAX17048 breakout (battery level) | 1 | 1 | 6 | address 0x36 |
| **Waveshare SIM7600E-H 4G HAT** | – | 1 | 90–100 | jumpers: UART B, PWR → D6, Flight open |
| LTE flex antenna (FPC, U.FL), 700–2700 MHz | – | 1–2 | 5–10 | main and optional diversity antenna |
| Active GNSS antenna, ceramic 25 × 25 mm, U.FL | – | 1 | 5–8 | into the frame at the top right of the top shell |
| Nano SIM with a **VoLTE** voice plan | – | 1 | contract | test VoLTE first (README) |

## Audio

| Part | L | H | approx. € | Note |
|---|---|---|---|---|
| Earpiece capsule Ø 15 mm, 32 Ω | 1 | 1 | 3 | into the holder under the head part |
| Speaker Ø 28 mm, 8 Ω, ≥ 1 W | 1 | 1 | 3 | bottom of the handset back |
| Electret microphone capsule Ø 9.7 mm (2-pin) | 1 | 1 | 1 | glue in with felt/sealing ring |
| Signal relay 2 × changeover, 5 V coil (e.g. TQ2/G6K type) | 1 | 1 | 3 | switches the speaker to the cradle automatically |
| Diode 1N4148 | 2 | 2 | 0.2 | flyback for relay and vibration motor |
| Resistor 10 kΩ, capacitor 1 µF (film/ceramic) | – | 6 / 2 | 1 | passive mixer modem audio + sound card (wiring §6) |
| 3.5 mm jack plug, 4-pole (CTIA), or solder points on the HAT | – | 1 | 1 | audio from/to the modem |

## Controls

| Part | L | H | approx. € | Note |
|---|---|---|---|---|
| Cherry MX format switches, plate mount (3 pins), **tactile** recommended | 17 | 17 | 10–15 | 16 keys + emergency; a noticeable actuation point helps with counting |
| Tactile switch 6 × 6 × 5 mm + perfboard 14 × 16 mm | 2 | 2 | 1 | volume +/− |
| Reed contact (glass, approx. 2 × 14 mm) + magnet 5 × 1 mm | 1 | 1 | 2 | emergency cover; alternatively a Hall switch |
| LED 5 mm, bright (warm white or yellow) | 1 | 1 | 0.5 | message indicator in the head part |
| Resistor 100 Ω / 10 kΩ | 3 / 2 | 3 / 2 | 0.5 | LED series resistor and 2 gate resistors / 2 gate pull-downs |
| N-MOSFET logic level (AO3400 or 2N7000) | 2 | 2 | 1 | LED (bright from 5 V) and vibration motor |
| Vibration motor (coin Ø 10 mm, 3 V) | 1 | 1 | 1 | feel the ringing |

## Power supply

| Part | L | H | approx. € | Note |
|---|---|---|---|---|
| LiPo 1S with protection circuit, JST-PH | 3000 mAh (approx. 60 × 75 × 10) | 5000 mAh (approx. 60 × 70 × 12) | 12–20 | measure it, bay in `omafon_gehaeuse.scad` (`AK`) |
| Charge/path controller with bq24074 and PGOOD output | 1 | 1 | 10–15 | e.g. Adafruit “bq24074 Universal Charger” |
| Boost converter 3.7 → 5 V | 1 A | **3 A** | 6–12 | hybrid: modem transmit peaks up to 2 A |
| Silicone wire 0.5 mm² (AWG 20), red/black | 0.5 m | 0.5 m | 2 | battery, converter, Pi, contacts |

## Charging contacts and cradle

| Part | L | H | approx. € | Note |
|---|---|---|---|---|
| Brass disc Ø 5 × 1 mm | 5 | 5 | 1 | contacts at the bottom of the handset |
| Steel disc Ø 8 × 1.5 mm | 2 | 2 | 0.5 | counterpart to the magnets |
| Spring contact (pogo pin) Ø 2 mm, travel ≥ 1 mm | 5 | 5 | 4 | into the contact carrier of the cradle |
| Neodymium magnet 8 × 3 mm | 2 | 2 | 2 | polarity such that they attract the steel discs |
| Full-range speaker Ø 50 mm, 8 Ω, ≥ 3 W | 1 | 1 | 6–10 | ringing and hands-free in the cradle |
| USB-C socket board with 5.1 kΩ CC resistors | 1 | 1 | 2 | without CC resistors a USB-C power supply delivers no power |
| USB-C power supply 5 V / 3 A | 1 | 1 | 10 | |
| Steel discs approx. 150–250 g, 4 rubber feet Ø 10 mm | 1 set | 1 set | 4 | stability |

## Handset mechanics

| Part | L | H | approx. € | Note |
|---|---|---|---|---|
| Threaded insert M2.5 × 3.5 (Ø 3.6 mm hole) | 6 (+1) | 6 (+1) | 2 | +1 for the test piece |
| Cylinder head screw M2.5 × 25 / × 30 | 4 × 25 | 4 × 30 | 1 | housing, from the back |
| Countersunk screw M2.5 × 6 | 2 | 2 | 0.5 | battery cover |
| Screw M2.5 × 6 (thread-forming) | 4 | 4 | 0.5 | Pi onto the standoffs |
| M3 × 8 | 2 | 2 | 0.3 | base of the cradle |
| Filament 1.75 mm, 32 mm long | 1 | 1 | – | hinge pin of the emergency cover |

## Consumables

| Part | Quantity | approx. € |
|---|---|---|
| PETG (housing, cradle, caps) | approx. 450 g (hybrid approx. 500 g) | 12 |
| TPU 95A (ear cup) | leftover, < 5 g | – |
| Wire 0.14 mm² (AWG 26), several colors | approx. 3 m | 3 |
| Heat shrink, cable ties 2.5 mm, double-sided adhesive pads | – | 4 |
| 2-part epoxy (head part, magnets, discs), superglue with primer (TPU) | – | 6 |

## Totals (estimate)

| | Landline | Hybrid |
|---|---|---|
| Electronics, audio, controls | approx. €95–115 | approx. €210–240 |
| Power, charging contacts, cradle | approx. €55–70 | approx. €65–80 |
| Mechanics, consumables | approx. €25–30 | approx. €25–30 |
| **Total** | **approx. €175–215** | **approx. €300–350** plus SIM contract |
