# Wiring

*English · [Deutsch](verkabelung.de.md)*

Applies to **landline** and **hybrid**. What only the hybrid adds is marked
**(H)**. The pin assignment must match `omafon/hardware.py`
(`MCP_KEYS`, `PI_INPUTS`, `PIN_VIBRA`, `PIN_LED`, `PIN_MODEM_PWR`). When changing it,
always update both places – and both language versions of this page (a test checks
them). Parts: [stueckliste.md](stueckliste.md).

> **Status:** derived from the code, the breakout datasheets and the housing. Not
> yet measured on a prototype. Check the points marked 🔍 on the first build.

## 1. Overview

```
                         ┌──────────── Handset ─────────────────────────────────────┐
 Cradle                  │                                                          │
 USB-C 5V ──┬─ Pogo 1 ───┼─ Pad 1 ─┬─> bq24074 IN      BAT <── LiPo 1S (JST)        │
            │            │         │        PGOOD ──────────────> GPIO27           │
 GND ───────┼─ Pogo 2+3 ─┼─ Pad 2+3│        SYS ──┬─> boost converter 5 V ──> Pi 5 V│
            │            │         │              ├─> TPA2016 VDD                   │
            │            │         │              └─> vibration motor (via MOSFET)  │
            │            │         └─> relay coil (only in the cradle)              │
 SPK 50 mm ─┴─ Pogo 4+5 ─┼─ Pad 4+5 ── relay NO / NC ── SPK 28 mm in the handset    │
                         │                    ▲ COM                                 │
                         │   CM108 ─L/R─> TPA2016 ── OUT R ┘   OUT L ──> earpiece   │
                         │   (USB)  <─── electret microphone                        │
                         │   I²C: MCP23017 (keys), TPA2016, MAX17048 (battery)      │
                         │   GPIO: SOS, cover, volume, charging, vibration, LED     │
                         │   (H) SIM7600 HAT on the header, audio via mixer         │
                         └──────────────────────────────────────────────────────────┘
```

## 2. Raspberry Pi Zero 2 W – pin assignment

| Pin | BCM | Signal | goes to | Note |
|---|---|---|---|---|
| 1 | – | 3.3 V | MCP23017 VDD + RESET, MAX17048 VIN, breakout I²C level | |
| 2, 4 | – | 5 V | boost converter output | powers the Pi and (H) the HAT through the header |
| 6, 9, 14, 20, 25, 30, 34, 39 | – | GND | common ground | at least 2 GND pins for the 5 V supply |
| 3 | 2 | I²C SDA | MCP23017, TPA2016, MAX17048 | pull-ups on the Pi (1.8 kΩ) and the breakouts |
| 5 | 3 | I²C SCL | same | |
| 8 / 10 | 14 / 15 | UART TX / RX | (H) SIM7600 via the HAT header | HAT jumper **UART = B**; `serial_port: /dev/ttyAMA0` |
| 31 | 6 | Modem PWRKEY | (H) HAT jumper **PWR → D6** | `PIN_MODEM_PWR`; landline: unused |
| 7 | 4 | (airplane mode) | (H) HAT jumper **leave Flight open** | not used |
| 15 | 22 | SOS button | emergency button → GND | internal pull-up |
| 16 | 23 | Emergency cover | reed contact → GND | magnet in the cover: closed = shut; inverted in code |
| 18 | 24 | Volume up | 6×6 switch → GND | internal pull-up |
| 22 | 25 | Volume down | 6×6 switch → GND | internal pull-up |
| 13 | 27 | In the cradle | bq24074 **PGOOD** | open drain, low = power from the cradle |
| 32 | 12 | Vibration (PWM) | gate MOSFET 1 (via 100 Ω) | 10 kΩ gate → GND |
| 33 | 13 | LED | gate MOSFET 2 (via 100 Ω) | 10 kΩ gate → GND |
| USB socket “USB” (not “PWR”) | – | USB | CM108 sound card | OTG adapter or directly to the test pads PP22 (D+) / PP23 (D−), 5 V, GND 🔍 |

## 3. Keypad (MCP23017, I²C 0x20)

- **Supply:** VDD → 3.3 V, VSS → GND, **RESET → 3.3 V** (otherwise random resets),
  A0/A1/A2 → GND (address 0x20).
- **Switches:** every Cherry MX switch has two pins. Pin 1 goes to its MCP input,
  pin 2 to a common **ground rail**: a bare wire soldered across all switches.
  Pull-ups are enabled in the MCP (register GPPU). No external resistors needed.
- Keep wires as short as possible, twisted with GND if longer than 15 cm.

| MCP pin | Bit | Key | | MCP pin | Bit | Key |
|---|---|---|---|---|---|---|
| GPA0 | 0 | 1 | | GPB0 | 8 | 9 |
| GPA1 | 1 | 2 | | GPB1 | 9 | * (star) |
| GPA2 | 2 | 3 | | GPB2 | 10 | 0 |
| GPA3 | 3 | 4 | | GPB3 | 11 | # (hash) |
| GPA4 | 4 | 5 | | GPB4 | 12 | Call (yellow) |
| GPA5 | 5 | 6 | | GPB5 | 13 | Hang up (black) |
| GPA6 | 6 | 7 | | GPB6 | 14 | Message |
| GPA7 | 7 | 8 | | GPB7 | 15 | Info |

The **emergency button** is deliberately **not** on the MCP but directly on GPIO22.
If the I²C bus fails, the emergency call still works (rule 2 in `CLAUDE.md`).

## 4. Further inputs

| Part | Connection | Note |
|---|---|---|
| Emergency button (MX, in the emergency recess) | GPIO22 ↔ GND | stranded wire through the recess to the inside |
| Reed contact (channel next to the recess) | GPIO23 ↔ GND | bend the glass carefully, bend the legs at least 2 mm away from the glass |
| Volume up / down (6×6 on perfboard in the rails) | GPIO24 / GPIO25 ↔ GND | upper switch = louder (cap with cross) |
| bq24074 PGOOD | GPIO27 | no external pull-up needed (internal pull-up of the Pi) |

## 5. Outputs

**Vibration motor:**
```
SYS (3.5–4.2 V) ── motor + ── motor − ── drain MOSFET 1 ── source ── GND
                    └─ 1N4148 (cathode to SYS) ─┘
GPIO12 ── 100 Ω ── gate MOSFET 1        gate ── 10 kΩ ── GND
```
The code limits PWM to 80 % so the 3 V motor is not overloaded.

**LED (in the head part, bright from 5 V):**
```
5 V ── 100 Ω ── LED anode ── LED cathode ── drain MOSFET 2 ── source ── GND
GPIO13 ── 100 Ω ── gate MOSFET 2        gate ── 10 kΩ ── GND
```
That gives about 20 mA. With good residual vision, prefer 220 Ω so the LED doesn’t
dazzle at night. The wires run through the LED hole in the top into the light pipe
of the head part.

## 6. Audio

| From | To | Note |
|---|---|---|
| CM108 headphone L | TPA2016 IN L (+), GND → IN L (−) | earpiece channel |
| CM108 headphone R | TPA2016 IN R (+), GND → IN R (−) | speaker channel |
| TPA2016 OUT L+ / L− | earpiece 32 Ω | **bridged output:** no output to GND |
| TPA2016 OUT R+ / R− | relay **COM** (both contact sets) | |
| relay **NC** (rest) | speaker 28 mm in the handset | phone in the hand |
| relay **NO** (active) | pad 4 / pad 5 → cradle speaker | phone in the cradle |
| relay coil | pad 1 (+5 V from the cradle) ↔ GND, 1N4148 anti-parallel | switches without software |
| electret microphone + / − | CM108 MIC / GND | bias comes from the CM108 |
| TPA2016 VDD / GND / SDA / SCL | SYS / GND / I²C | address 0x58; SHDN → VDD (always on, the software switches the channels) |

**(H) Audio from and to the modem.** The SIM7600 has its own audio codec on the
4-pole jack of the HAT (CTIA: tip = L, ring 1 = R, ring 2 = GND, sleeve = microphone).
So that grandma hears LTE calls through the same earpiece, both sources are mixed
passively:

```
CM108 L ── 10 kΩ ──┬── TPA2016 IN L+          CM108 R ── 10 kΩ ──┬── TPA2016 IN R+
Modem L ── 10 kΩ ──┘                          Modem R ── 10 kΩ ──┘
microphone (on CM108 MIC) ── 1 µF ── 10 kΩ ── modem MIC (sleeve)
```

🔍 Check the level on the prototype and adjust the mixer if needed (e.g. 4.7 kΩ for the
quieter source). The modem microphone then also carries its own bias. If it sounds
distorted, connect a **second electret capsule** directly to the modem (there is room
in the microphone holder).

## 7. Power supply

| From | To | Cross-section |
|---|---|---|
| pad 1 (+5 V cradle) | bq24074 **IN** and relay coil | 0.5 mm² |
| pad 2 + 3 | GND | 0.5 mm² |
| LiPo (JST-PH) | bq24074 **BAT** | 0.5 mm²; the connector is the disconnect point for maintenance |
| bq24074 **SYS/OUT** | boost converter IN, TPA2016 VDD, vibration motor | 0.5 mm² |
| boost converter 5 V OUT | Pi pin 2 + 4, GND to pin 6 + 14 | 0.5 mm²; (H) 3 A converter, short wires |
| LiPo + / − | MAX17048 CELL+ / GND | thin; measures directly at the battery |

- The bq24074 charges from the cradle and powers the phone at the same time (power path).
  🔍 Set or check the charging current on the board at 1 A.
- On the Pi, the 5 V go through the header, i.e. bypassing the polyfuse. So only connect
  the regulated converter, never the battery directly.
- (H) The modem draws up to 2 A when transmitting. Hence a 3 A converter, thick and short
  wires, a 470 µF electrolytic capacitor at the Pi’s 5 V pins. 🔍 If it crashes during
  calls, first measure the voltage at pin 2 while transmitting.

## 8. Charging cradle

| From | To | Note |
|---|---|---|
| USB-C VBUS | spring contact 1 (+5 V) | contact 1 is marked on the carrier |
| USB-C GND | spring contacts 2 and 3 | two contacts for lower contact resistance |
| speaker 50 mm + / − | spring contacts 4 / 5 | |
| USB-C CC1 / CC2 | 5.1 kΩ each → GND | already fitted on most breakouts 🔍 |

Contact order 1–5 **from the left, looking at the front of the phone**, the same in the
handset and the cradle. The coding rib prevents inserting it the wrong way.

## 9. First power-up (before closing the housing)

1. **Without the Pi:** connect the battery and the cradle. Measure 5.0–5.2 V at the
   converter output. The relay must click when the handset sits in the cradle.
2. Connect and boot the Pi: `i2cdetect -y 1` shows **0x20, 0x36, 0x58**.
3. `aplay -l` / `arecord -l` show the CM108. `speaker-test -D plughw:CARD=Device -c 2`
   plays on the earpiece (L) and the speaker (R). Omafon must be running first, or the
   TPA2016 switched on via I²C.
4. Keys: start Omafon in the foreground
   (`python3 -m omafon.main --config /etc/omafon/config.yaml -v`). Every key must be
   announced immediately. Test the emergency call with the cover open, and **release it
   before the 3 seconds are up**.
5. (H) Modem test from the README (`minicom`, VoLTE call), then check the audio through
   the mixer.
