# Festnetz-Variante: Hardware

Gegenüber dem Hybridgerät entfallen **Modem, SIM und GPS**. Neu sind die
**Ladeschale mit Lautsprecher** und die **Federkontakte**. Tasten, Notrufknopf
mit Klappe, Verstärker, Hörkapsel, Mikrofon und Akku-Messung bleiben gleich, ebenso
die Software-Schicht dafür (`hardware.py`, `audio.py`).

Preise sind **grobe Schätzungen** (Stand Ende 2026, Einzelstück, inkl. MwSt., ohne
Versand). Nur Pi und Modem habe ich gegen Händlerangaben geprüft [1, 2].

## Stückliste Handteil

| # | Teil | Zweck | ca. € |
|---|---|---|---|
| 1 | Raspberry Pi Zero 2 W (ohne Stiftleiste) | Rechner, **WLAN 2,4 GHz** | 18–24 [1] |
| 2 | microSD 32 GB „High Endurance“ | System (schreibgeschützt, Overlay-FS) | 10 |
| 3 | USB-Soundkarte CM108 (Platine ohne Gehäuse) | Ton ein/aus | 6–8 |
| 4 | TPA2016D2-Verstärker-Breakout | L = Hörkapsel, R = Lautsprecher, AGC/Limiter | 10 |
| 5 | Hörkapsel 32 Ω, Lautsprecher 28 mm 8 Ω | Gespräch am Ohr, Klingeln im Handteil | 5 |
| 6 | Elektret- oder MEMS-Mikrofon | Sprechen, Sprachwahl, Diktat | 3 |
| 7 | MCP23017-Breakout | 16 Tasten über I²C | 4 |
| 8 | 16 Taster im Cherry-MX-Format + gedruckte Kappen | Tastenfeld (`cad/omafon_tasten.scad`) | 10 |
| 9 | Notrufknopf + Mikroschalter für die Klappe | SOS direkt am GPIO (nicht über I²C) | 5 |
| 10 | 2 Taster Lautstärke | direkt am GPIO | 1 |
| 11 | LiPo 1S **3000 mAh** mit Schutzschaltung | Akku (Begründung unten) | 12–15 |
| 12 | Lade-/Pfadregler mit bq24074 (PGOOD-Ausgang) | Laden aus der Schale, Ladeerkennung | 10–15 |
| 13 | Aufwärtswandler 3,7 → 5 V, **1 A** genügt | Pi-Versorgung (vorher 2–3 A wegen Modem) | 6–8 |
| 14 | MAX17048-Breakout | Akkustand in Prozent | 6 |
| 15 | Vibrationsmotor, helle LED | Klingeln fühlen, Nachrichtenanzeige | 3 |
| 16 | **Signalrelais 2× UM, 5 V** (z. B. Bauform TQ2/G6K) + Freilaufdiode | Lautsprecher automatisch auf die Schale umschalten | 3 |
| 17 | Kontaktplatte: 5 Messingscheiben Ø5 mm, 2 Stahlscheiben | Gegenstück zu den Federkontakten (`handteil_kontakte`) | 3 |
| | **Summe Handteil** | | **ca. 120–145** |

## Stückliste Ladeschale

| # | Teil | Zweck | ca. € |
|---|---|---|---|
| 1 | 5 Federkontakte (Pogo-Pins) Ø2 mm, Hub ≥ 1 mm | +5 V, 2× GND, LS+, LS− | 4 |
| 2 | 2 Magnete 8 × 3 mm (Neodym) | Telefon rastet fühlbar ein | 2 |
| 3 | Breitband-Lautsprecher 50 mm, 8 Ω, ≥ 3 W | Klingeln und Freisprechen in der Schale | 6–10 |
| 4 | USB-C-Buchsenplatine (mit 5,1-kΩ-CC-Widerständen) | Stromeingang | 2 |
| 5 | USB-C-Netzteil 5 V / 3 A | Versorgung | 10 |
| 6 | Stahlscheiben ca. 150–250 g, 4 Gummifüße, 2 Schrauben M3 | Standfestigkeit, rutschfest | 4 |
| 7 | PETG ca. 150 g | `cad/omafon_ladeschale.scad` | 4 |
| | **Summe Ladeschale** | | **ca. 30–35** |

**Gesamt ca. 150–180 €.** Es entfallen gegenüber Mobilfunk: SIM7600E-H-HAT
(ca. 90–100 € [2]), LTE- und GNSS-Antennen (ca. 10 €), SIM-Vertrag.

## Strombilanz und Akku

| Zustand | Leistung (geschätzt) | Quelle/Annahme |
|---|---|---|
| Pi Zero 2 W in Ruhe, WLAN verbunden | ca. 0,60 W | 120 mA bei 5 V, WLAN +11 mA [3] |
| Pi optimiert (HDMI, Bluetooth, Kamera-Erkennung aus) | ca. 0,46–0,50 W | 92,7 mA [3] |
| Verstärker abgeschaltet, MCP23017, MAX17048, LED blinkend | ca. 0,03 W | Datenblattwerte, grob |
| Gespräch (WLAN aktiv, Audio, baresip) | ca. 1,2–1,5 W | Annahme, am Gerät messen |
| *zum Vergleich: SIM7600 in Ruhe* | *ca. 0,1 W*, Sendespitzen bis 2 A | Hybridgerät |

Rechnung 3000 mAh: 3,7 V × 3,0 Ah = 11,1 Wh; nach Wandlern (ca. 85 %) etwa 9,4 Wh.
- Bereitschaft: 9,4 Wh ÷ 0,63 W ≈ **15 h**, optimiert ÷ 0,5 W ≈ **19 h**
- Gesprächszeit: 9,4 Wh ÷ 1,35 W ≈ **7 h**

**Folgerung:** Das Telefon gehört nachts und meist auch tagsüber in die Schale.
Abheben nimmt an, Einstellen legt auf, das passt dazu. Ein **kleinerer Akku**
(z. B. 1500 mAh, etwa 7–9 h Bereitschaft) ginge technisch, weil keine 2-A-Spitzen
mehr anfallen. Für eine Person, die das Telefon auch mal im Sessel liegen lässt,
empfehle ich ihn aber nicht. Die Akkuwarnungen bei 20/10/5 % kommen weiter per
Ansage.

## WLAN-Antenne

- Der Pi Zero 2 W hat **nur eine Platinenantenne** und keinen Antennenanschluss.
  Ein U.FL-Umbau ist möglich, hebt aber die Funkzulassung auf [4]. **Nicht machen.**
- Platine so einbauen, dass die Antenne (Schmalseite neben dem Mini-HDMI) **oben im
  Gehäuse** liegt, nicht vom Akku verdeckt. Keine Metallfolie, keine Schrauben und
  keine Leiterbahnen anderer Platinen im Umkreis von ca. 10 mm.
- Empfang prüfen: Info-Taste sagt „Verbindung zur Fritzbox gut/mittel/schwach“
  (Schwellen −67 / −75 dBm). Ist es an Omas Lieblingsplatz „schwach“: Fritz!Repeater
  im Mesh. Nicht das Telefon umbauen.
- Nur 2,4 GHz. In der Fritz!Box das 2,4-GHz-Band an lassen.

## Verkabelung

### GPIO und I²C (wie Mobilfunk, außer Modem)

| Signal | Pi-Pin (BCM) | Bemerkung |
|---|---|---|
| I²C SDA/SCL | 2 / 3 | MCP23017 0x20, TPA2016 0x58, MAX17048 0x36 |
| SOS-Knopf | 22 | direkt, **nicht über I²C** (Notruf geht auch bei I²C-Fehler) |
| SOS-Klappe (Mikroschalter) | 23 | invertiert |
| Lauter / Leiser | 24 / 25 | |
| **In der Schale** (bq24074 PGOOD) | 27 | low = Strom von der Schale = „eingestellt“ |
| Vibration (PWM) | 12 | über Transistor |
| LED | 13 | über Vorwiderstand/Transistor |
| ~~Modem PWRKEY~~ | ~~6~~ | **frei** |
| Soundkarte | USB (über Testpads oder OTG-Adapter) | |

### Strom und Kontakte

```
 Ladeschale                                     Handteil
 ──────────                                     ───────
 USB-C 5V ─┬─────────── Pogo 1 (+5V) ─── Pad 1 ─┬─> bq24074 IN ── Akku 1S
           │                                    │       │ PGOOD ──> GPIO27
           │                                    │       └─ SYS ──> Wandler 5V/1A ──> Pi 5V
           │                                    └─> Relais-Spule ─┐ (Freilaufdiode)
 GND ──────┴─────────── Pogo 2+3 (GND) ── Pad 2+3 ───────────────┘
                                                        TPA2016 Kanal R (BTL)
 Lautsprecher 50 mm ─── Pogo 4 (LS+) ──── Pad 4 ── Relais NO ─┐ ┌─ NC ── Lautsprecher 28 mm
                    └── Pogo 5 (LS−) ──── Pad 5 ── Relais NO ─┘ └─ NC ── (im Handteil)
```

- Das **Relais schaltet ohne Software**. Liegt Schalenspannung an, geht der
  Lautsprecherkanal auf die Schale, sonst auf den kleinen Lautsprecher im Handteil.
  Hängt die Software, klingelt es trotzdem dort, wo das Telefon steht.
- Die Spule hängt an der Schalenspannung, belastet den Akku also nicht.
- Die Software weiß über PGOOD (GPIO 27), dass das Telefon steht. Mit
  `dock_speaker: true` legt sie Gespräche in der Schale auf den Lautsprecherkanal.
- Der TPA2016 ist ein Klasse-D-Verstärker mit Brückenausgang. **Kein Ausgang darf an
  GND**, deshalb das zweipolige Relais. Lautsprecherleitungen kurz halten, bei
  Störungen Ferrit.
- Zwei GND-Kontakte: geringerer Übergangswiderstand beim Laden (bis ca. 1 A).
- Kontaktreihenfolge 1–5 von links (Blick von vorn). Der Kontaktträger hat eine
  Markierung an Kontakt 1. Die Kodierrippe verhindert falsches Einstecken.

### Bedienung an der Schale (Software, `config.festnetz.example.yaml`)

| Einstellung | Wirkung |
|---|---|
| `answer_on_lift: true` | Klingelt es und Oma nimmt das Telefon aus der Schale, ist sie verbunden |
| `dock_in_call: hangup` | Zurückstellen beendet das Gespräch (wie ein klassischer Hörer) |
| `dock_in_call: handsfree` | Zurückstellen schaltet auf Freisprechen über die Schale |
| `dock_speaker: true` | Annehmen per Taste in der Schale = Freisprechen über die Schale |

## Quellen

1. Notebookcheck (BerryBase-/Welectron-Preise Pi Zero 2 W) – https://www.notebookcheck.com/Deal-Raspberry-Pi-Zero-2-W-fuer-faire-24-Euro-sofort-verfuegbar.735276.0.html , https://www.notebookcheck.com/Deal-Raspberry-Pi-Zero-2-W-zum-vernuenftigen-Preis-sofort-verfuegbar.605703.0.html
2. buyzero.de / eBay (SIM7600G-H-HAT 90–100 €; E-H-Preis in € nicht gefunden) – https://buyzero.de/products/waveshare-19485-sim7600g-h-4g-hat-b
3. CNX Software: Raspberry Pi Zero 2 W power consumption – https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/
4. Brian Dorey: Zero 2 W external antenna mod; Tom's Hardware dazu – https://www.briandorey.com/post/raspberry-pi-zero-2-w-external-antenna-mod , https://tomshardware.com/news/raspberry-pi-zero-2-w-external-antenna-mod
