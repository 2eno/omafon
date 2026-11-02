# Verkabelung

Gilt für **Festnetz** und **Hybrid**. Was nur beim Hybrid dazukommt, ist mit
**(H)** markiert. Die Pinbelegung muss mit `omafon/hardware.py` übereinstimmen
(`MCP_KEYS`, `PI_INPUTS`, `PIN_VIBRA`, `PIN_LED`, `PIN_MODEM_PWR`). Bei Änderungen
immer beide Stellen anpassen. Bauteile: [stueckliste.md](stueckliste.md).

> **Stand:** abgeleitet aus Code, Datenblattangaben der Breakouts und dem
> Gehäuse. Am Muster noch nicht nachgemessen. Mit 🔍 markierte Punkte beim
> ersten Aufbau prüfen.

## 1. Übersicht

```
                         ┌──────────── Handteil ────────────────────────────────────┐
 Ladeschale              │                                                          │
 USB-C 5V ──┬─ Pogo 1 ───┼─ Pad 1 ─┬─> bq24074 IN      BAT <── LiPo 1S (JST)        │
            │            │         │        PGOOD ──────────────> GPIO27           │
 GND ───────┼─ Pogo 2+3 ─┼─ Pad 2+3│        SYS ──┬─> Aufwärtswandler 5 V ──> Pi 5 V│
            │            │         │              ├─> TPA2016 VDD                   │
            │            │         │              └─> Vibrationsmotor (über MOSFET) │
            │            │         └─> Relaisspule (nur in der Schale)              │
 LS 50 mm ──┴─ Pogo 4+5 ─┼─ Pad 4+5 ── Relais NO / NC ── LS 28 mm im Handteil      │
                         │                    ▲ COM                                 │
                         │   CM108 ─L/R─> TPA2016 ── OUT R ┘   OUT L ──> Hörkapsel  │
                         │   (USB)  <─── Elektret-Mikrofon                          │
                         │   I²C: MCP23017 (Tasten), TPA2016, MAX17048 (Akku)       │
                         │   GPIO: Notruf, Klappe, Lautstärke, Laden, Vibration, LED│
                         │   (H) SIM7600-HAT auf der Stiftleiste, Ton über Mischer   │
                         └──────────────────────────────────────────────────────────┘
```

## 2. Raspberry Pi Zero 2 W – Pinbelegung

| Pin | BCM | Signal | geht an | Hinweis |
|---|---|---|---|---|
| 1 | – | 3,3 V | MCP23017 VDD + RESET, MAX17048 VIN, Breakout-I²C-Pegel | |
| 2, 4 | – | 5 V | Ausgang Aufwärtswandler | versorgt Pi und (H) HAT über die Stiftleiste |
| 6, 9, 14, 20, 25, 30, 34, 39 | – | GND | gemeinsame Masse | mindestens 2 GND-Pins für die 5-V-Zuleitung |
| 3 | 2 | I²C SDA | MCP23017, TPA2016, MAX17048 | Pull-ups auf dem Pi (1,8 kΩ) und den Breakouts |
| 5 | 3 | I²C SCL | dito | |
| 8 / 10 | 14 / 15 | UART TX / RX | (H) SIM7600 über die HAT-Stiftleiste | HAT-Jumper **UART = B**; `serial_port: /dev/ttyAMA0` |
| 31 | 6 | Modem PWRKEY | (H) HAT-Jumper **PWR → D6** | `PIN_MODEM_PWR`; Festnetz: frei |
| 7 | 4 | (Flugmodus) | (H) HAT-Jumper **Flight offen lassen** | wird nicht benutzt |
| 15 | 22 | SOS-Taster | Notruftaster → GND | interner Pull-up |
| 16 | 23 | Notrufklappe | Reedkontakt → GND | Magnet in der Klappe: zu = geschlossen; im Code invertiert |
| 18 | 24 | Lauter | 6×6-Taster → GND | interner Pull-up |
| 22 | 25 | Leiser | 6×6-Taster → GND | interner Pull-up |
| 13 | 27 | In der Schale | bq24074 **PGOOD** | Open-Drain, low = Strom von der Schale |
| 32 | 12 | Vibration (PWM) | Gate MOSFET 1 (über 100 Ω) | 10 kΩ Gate → GND |
| 33 | 13 | LED | Gate MOSFET 2 (über 100 Ω) | 10 kΩ Gate → GND |
| USB-Buchse „USB“ (nicht „PWR“) | – | USB | CM108-Soundkarte | OTG-Adapter oder direkt an die Testpads PP22 (D+) / PP23 (D−), 5 V, GND 🔍 |

## 3. Tastenfeld (MCP23017, I²C 0x20)

- **Versorgung:** VDD → 3,3 V, VSS → GND, **RESET → 3,3 V** (sonst zufällige Resets),
  A0/A1/A2 → GND (Adresse 0x20).
- **Taster:** Jeder Cherry-MX-Taster hat zwei Pins. Pin 1 geht an seinen
  MCP-Eingang, Pin 2 an eine gemeinsame **Masse-Schiene**: blanker Draht,
  der quer über alle Taster gelötet ist. Pull-ups sind im MCP eingeschaltet
  (Register GPPU). Externe Widerstände sind nicht nötig.
- Leitungen so kurz wie möglich, verdrillt mit GND, wenn sie länger als 15 cm sind.

| MCP-Pin | Bit | Taste | | MCP-Pin | Bit | Taste |
|---|---|---|---|---|---|---|
| GPA0 | 0 | 1 | | GPB0 | 8 | 9 |
| GPA1 | 1 | 2 | | GPB1 | 9 | * (Stern) |
| GPA2 | 2 | 3 | | GPB2 | 10 | 0 |
| GPA3 | 3 | 4 | | GPB3 | 11 | # (Raute) |
| GPA4 | 4 | 5 | | GPB4 | 12 | Anrufen (gelb) |
| GPA5 | 5 | 6 | | GPB5 | 13 | Auflegen (schwarz) |
| GPA6 | 6 | 7 | | GPB6 | 14 | Nachricht |
| GPA7 | 7 | 8 | | GPB7 | 15 | Info |

Der **Notruftaster** hängt bewusst **nicht** am MCP, sondern direkt an GPIO22.
Fällt der I²C-Bus aus, funktioniert der Notruf trotzdem (Regel 2 in `CLAUDE.md`).

## 4. Weitere Eingänge

| Bauteil | Anschluss | Hinweis |
|---|---|---|
| Notruftaster (MX, in der Notrufmulde) | GPIO22 ↔ GND | Litze durch die Mulde nach innen |
| Reedkontakt (Kanal neben der Mulde) | GPIO23 ↔ GND | Glas vorsichtig biegen, Beine mindestens 2 mm vom Glas entfernt abwinkeln |
| Lauter / Leiser (6×6 auf Lochraster in den Schienen) | GPIO24 / GPIO25 ↔ GND | oberer Taster = lauter (Kappe mit Kreuz) |
| bq24074 PGOOD | GPIO27 | kein externer Pull-up nötig (interner Pull-up des Pi) |

## 5. Ausgänge

**Vibrationsmotor:**
```
SYS (3,5–4,2 V) ── Motor + ── Motor − ── Drain MOSFET 1 ── Source ── GND
                    └─ 1N4148 (Kathode an SYS) ─┘
GPIO12 ── 100 Ω ── Gate MOSFET 1        Gate ── 10 kΩ ── GND
```
Der Code begrenzt per PWM auf 80 %, damit der 3-V-Motor nicht überlastet wird.

**LED (im Hörerkopf, hell aus 5 V):**
```
5 V ── 100 Ω ── LED Anode ── LED Kathode ── Drain MOSFET 2 ── Source ── GND
GPIO13 ── 100 Ω ── Gate MOSFET 2        Gate ── 10 kΩ ── GND
```
Ergibt ca. 20 mA. Bei hoher Restsehkraft lieber 220 Ω, damit die LED nachts nicht blendet.
Die Drähte laufen durch das LED-Loch im Deckel in das Lichtrohr des Hörerkopfs.

## 6. Audio

| Von | Nach | Hinweis |
|---|---|---|
| CM108 Kopfhörer L | TPA2016 IN L (+), GND → IN L (−) | Hörkapsel-Kanal |
| CM108 Kopfhörer R | TPA2016 IN R (+), GND → IN R (−) | Lautsprecher-Kanal |
| TPA2016 OUT L+ / L− | Hörkapsel 32 Ω | **Brückenausgang:** kein Ausgang an GND |
| TPA2016 OUT R+ / R− | Relais **COM** (beide Kontaktsätze) | |
| Relais **NC** (Ruhe) | Lautsprecher 28 mm im Handteil | Telefon in der Hand |
| Relais **NO** (Arbeit) | Pad 4 / Pad 5 → Schalenlautsprecher | Telefon in der Schale |
| Relais Spule | Pad 1 (+5 V aus der Schale) ↔ GND, 1N4148 antiparallel | schaltet ohne Software |
| Elektret-Mikrofon + / − | CM108 MIC / GND | Vorspannung kommt von der CM108 |
| TPA2016 VDD / GND / SDA / SCL | SYS / GND / I²C | Adresse 0x58; SHDN → VDD (immer an, Kanäle schaltet die Software) |

**(H) Ton vom und zum Modem.** Der SIM7600 hat einen eigenen Audio-Codec am
4-poligen Klinkenanschluss des HAT (CTIA: Spitze = L, Ring 1 = R, Ring 2 = GND,
Hülse = Mikrofon). Damit Oma LTE-Gespräche über dieselbe Hörkapsel hört, werden
beide Quellen passiv gemischt:

```
CM108 L ── 10 kΩ ──┬── TPA2016 IN L+          CM108 R ── 10 kΩ ──┬── TPA2016 IN R+
Modem L ── 10 kΩ ──┘                          Modem R ── 10 kΩ ──┘
Mikrofon (an CM108 MIC) ── 1 µF ── 10 kΩ ── Modem MIC (Hülse)
```

🔍 Den Pegel am Muster prüfen und den Mischer ggf. anpassen (z. B. 4,7 kΩ für die
leisere Quelle). Am Modem-Mikrofon liegt dann zusätzlich dessen eigene
Vorspannung. Klingt es verzerrt, eine **zweite Elektretkapsel** direkt ans Modem
legen (Platz ist im Mikrofonhalter).

## 7. Stromversorgung

| Von | Nach | Querschnitt |
|---|---|---|
| Pad 1 (+5 V Schale) | bq24074 **IN** und Relaisspule | 0,5 mm² |
| Pad 2 + 3 | GND | 0,5 mm² |
| LiPo (JST-PH) | bq24074 **BAT** | 0,5 mm²; der Stecker ist die Trennstelle für Wartung |
| bq24074 **SYS/OUT** | Aufwärtswandler IN, TPA2016 VDD, Vibrationsmotor | 0,5 mm² |
| Aufwärtswandler 5 V OUT | Pi Pin 2 + 4, GND an Pin 6 + 14 | 0,5 mm²; (H) Wandler 3 A, Leitungen kurz |
| LiPo + / − | MAX17048 CELL+ / GND | dünn; misst direkt am Akku |

- Der bq24074 lädt aus der Schale und versorgt das Telefon gleichzeitig (Power-Path).
  🔍 Den Ladestrom auf dem Board auf 1 A einstellen bzw. prüfen.
- Die 5 V gehen am Pi über die Stiftleiste, also an der Polyfuse vorbei. Deshalb nur
  den geregelten Wandler anschließen, nie direkt den Akku.
- (H) Das Modem zieht beim Senden bis 2 A. Deshalb Wandler 3 A, dicke und kurze
  Leitungen, 470-µF-Elko an den 5-V-Pins des Pi. 🔍 Bei Abstürzen während
  Gesprächen zuerst die Spannung an Pin 2 beim Senden messen.

## 8. Ladeschale

| Von | Nach | Hinweis |
|---|---|---|
| USB-C VBUS | Federkontakt 1 (+5 V) | Kontakt 1 ist am Träger markiert |
| USB-C GND | Federkontakte 2 und 3 | zwei Kontakte für geringeren Übergangswiderstand |
| Lautsprecher 50 mm + / − | Federkontakte 4 / 5 | |
| USB-C CC1 / CC2 | je 5,1 kΩ → GND | auf den meisten Breakouts schon bestückt 🔍 |

Kontaktreihenfolge 1–5 **von links bei Blick auf die Vorderseite des Telefons**,
im Handteil wie in der Schale gleich. Die Kodierrippe verhindert falsches Einstecken.

## 9. Erste Inbetriebnahme (vor dem Schließen des Gehäuses)

1. **Ohne Pi:** Akku anstecken, Schale anschließen. Am Wandlerausgang 5,0–5,2 V
   messen. Das Relais muss klicken, wenn das Handteil in der Schale steht.
2. Pi anschließen und booten: `i2cdetect -y 1` zeigt **0x20, 0x36, 0x58**.
3. `aplay -l` / `arecord -l` zeigen die CM108. `speaker-test -D plughw:CARD=Device -c 2`
   spielt auf Hörkapsel (L) und Lautsprecher (R). Vorher muss Omafon laufen oder der
   TPA2016 per I²C eingeschaltet sein.
4. Tasten: Omafon im Vordergrund starten
   (`python3 -m omafon.main --config /etc/omafon/config.yaml -v`). Jede Taste muss
   sofort angesagt werden. Den Notruf bei geöffneter Klappe antesten, dabei **vor
   Ablauf der 3 Sekunden loslassen**.
5. (H) Modem-Test aus der README (`minicom`, VoLTE-Anruf), danach Ton über den
   Mischer prüfen.
