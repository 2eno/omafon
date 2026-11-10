# Stückliste

*[English](stueckliste.md) · Deutsch*

Für beide Varianten: **Festnetz** (Fritz!Box per WLAN, `backend: sip`) und
**Hybrid** (zusätzlich LTE-Modem für unterwegs, `backend: hybrid`). Die Spalten
„F“ und „H“ geben die Stückzahl je Variante an.

Preise sind **Schätzungen** für Einzelstücke inklusive MwSt., ohne Versand (Stand
Ende 2026). Geprüft gegen Händlerangaben sind nur Pi und Modem-HAT, siehe
[festnetz-hardware.md](festnetz-hardware.de.md#quellen). Anschlüsse:
[verkabelung.md](verkabelung.de.md). Gedruckte Teile und Montage:
[druckteile.md](druckteile.de.md).

## Elektronik

| Teil | F | H | ca. € | Hinweis |
|---|---|---|---|---|
| Raspberry Pi Zero 2 W (ohne Stiftleiste) | 1 | 1 | 18–24 | nur 2,4-GHz-WLAN; Platinenantenne nicht umbauen |
| Stiftleiste 2 × 20 (2,54 mm) | – | 1 | 1 | für den HAT; Festnetz: Kabel direkt anlöten |
| microSD 32 GB „High Endurance“ | 1 | 1 | 10 | System läuft mit Overlay-Dateisystem |
| USB-Soundkarte CM108 (Platine ohne Gehäuse) | 1 | 1 | 6–8 | Mikrofon-Bias liefert die Karte |
| Micro-USB-OTG-Adapter oder kurze Litze an die USB-Testpads | 1 | 1 | 2 | siehe Verkabelung |
| MCP23017-Breakout (I²C, 16 Eingänge) | 1 | 1 | 4 | Adresse 0x20 |
| TPA2016D2-Breakout (2 × Klasse-D, AGC) | 1 | 1 | 10 | L = Hörkapsel, R = Lautsprecher |
| MAX17048-Breakout (Akkustand) | 1 | 1 | 6 | Adresse 0x36 |
| **Waveshare SIM7600E-H 4G HAT** | – | 1 | 90–100 | Jumper: UART B, PWR → D6, Flight offen |
| LTE-Folienantenne (FPC, U.FL), 700–2700 MHz | – | 1–2 | 5–10 | Haupt- und optional Diversity-Antenne |
| GNSS-Antenne aktiv, Keramik 25 × 25 mm, U.FL | – | 1 | 5–8 | in den Rahmen oben rechts im Deckel |
| Nano-SIM mit **VoLTE**-Sprachtarif | – | 1 | Vertrag | VoLTE vorher testen (README.de.md) |

## Audio

| Teil | F | H | ca. € | Hinweis |
|---|---|---|---|---|
| Hörkapsel Ø 15 mm, 32 Ω | 1 | 1 | 3 | in den Halter unter dem Hörerkopf |
| Lautsprecher Ø 28 mm, 8 Ω, ≥ 1 W | 1 | 1 | 3 | Handteil-Rückseite unten |
| Elektret-Mikrofonkapsel Ø 9,7 mm (2-polig) | 1 | 1 | 1 | mit Filz/Dichtring einkleben |
| Signalrelais 2 × UM, Spule 5 V (z. B. Bauform TQ2/G6K) | 1 | 1 | 3 | schaltet den Lautsprecher automatisch auf die Schale |
| Diode 1N4148 | 2 | 2 | 0,2 | Freilauf Relais und Vibrationsmotor |
| Widerstand 10 kΩ, Kondensator 1 µF (Folie/Keramik) | – | 6 / 2 | 1 | passiver Mischer Modem-Ton + Soundkarte (Verkabelung §6) |
| Klinkenstecker 3,5 mm, 4-polig (CTIA), oder Lötpunkte am HAT | – | 1 | 1 | Ton vom/zum Modem |

## Bedienelemente

| Teil | F | H | ca. € | Hinweis |
|---|---|---|---|---|
| Taster im Cherry-MX-Format, Plattenmontage (3 Pins), **taktil** empfohlen | 17 | 17 | 10–15 | 16 Tasten + Notruf; fühlbarer Druckpunkt hilft beim Zählen |
| Kurzhubtaster 6 × 6 × 5 mm + Lochraster 14 × 16 mm | 2 | 2 | 1 | Lautstärke +/− |
| Reedkontakt (Glas, ca. 2 × 14 mm) + Magnet 5 × 1 mm | 1 | 1 | 2 | Notrufklappe; alternativ Hallschalter |
| LED 5 mm, hell (warmweiß oder gelb) | 1 | 1 | 0,5 | Nachrichtenanzeige im Hörerkopf |
| Widerstand 100 Ω / 10 kΩ | 3 / 2 | 3 / 2 | 0,5 | LED-Vorwiderstand und 2 Gate-Widerstände / 2 Gate-Pulldowns |
| N-MOSFET Logikpegel (AO3400 oder 2N7000) | 2 | 2 | 1 | LED (hell aus 5 V) und Vibrationsmotor |
| Vibrationsmotor (Münze Ø 10 mm, 3 V) | 1 | 1 | 1 | Klingeln fühlen |

## Stromversorgung

| Teil | F | H | ca. € | Hinweis |
|---|---|---|---|---|
| LiPo 1S mit Schutzschaltung, JST-PH | 3000 mAh (ca. 60 × 75 × 10) | 5000 mAh (ca. 60 × 70 × 12) | 12–20 | Maße nachmessen, Fach in `omafon_gehaeuse.scad` (`AK`) |
| Lade-/Pfadregler mit bq24074 und PGOOD-Ausgang | 1 | 1 | 10–15 | z. B. Adafruit „bq24074 Universal Charger“ |
| Aufwärtswandler 3,7 → 5 V | 1 A | **3 A** | 6–12 | Hybrid: Modem-Sendespitzen bis 2 A |
| Silikonlitze 0,5 mm² (AWG 20), rot/schwarz | 0,5 m | 0,5 m | 2 | Akku, Wandler, Pi, Kontakte |

## Ladekontakte und Ladeschale

| Teil | F | H | ca. € | Hinweis |
|---|---|---|---|---|
| Messingscheibe Ø 5 × 1 mm | 5 | 5 | 1 | Kontakte unten am Handteil |
| Stahlscheibe Ø 8 × 1,5 mm | 2 | 2 | 0,5 | Gegenstück zu den Magneten |
| Federkontakt (Pogo-Pin) Ø 2 mm, Hub ≥ 1 mm | 5 | 5 | 4 | in den Kontaktträger der Schale |
| Neodym-Magnet 8 × 3 mm | 2 | 2 | 2 | Polung so, dass sie die Stahlscheiben anziehen |
| Breitbandlautsprecher Ø 50 mm, 8 Ω, ≥ 3 W | 1 | 1 | 6–10 | Klingeln und Freisprechen in der Schale |
| USB-C-Buchsenplatine mit 5,1-kΩ-CC-Widerständen | 1 | 1 | 2 | ohne CC-Widerstände liefert ein USB-C-Netzteil keinen Strom |
| USB-C-Netzteil 5 V / 3 A | 1 | 1 | 10 | |
| Stahlscheiben ca. 150–250 g, 4 Gummifüße Ø 10 mm | 1 Satz | 1 Satz | 4 | Standfestigkeit |

## Mechanik Handteil

| Teil | F | H | ca. € | Hinweis |
|---|---|---|---|---|
| Gewindeeinsatz M2,5 × 3,5 (Ø 3,6 mm Loch) | 6 (+1) | 6 (+1) | 2 | +1 für das Prüfstück |
| Zylinderschraube M2,5 × 25 / × 30 | 4 × 25 | 4 × 30 | 1 | Gehäuse, von hinten |
| Senkschraube M2,5 × 6 | 2 | 2 | 0,5 | Akkudeckel |
| Schraube M2,5 × 6 (selbstformend) | 4 | 4 | 0,5 | Pi auf die Abstandshalter |
| M3 × 8 | 2 | 2 | 0,3 | Boden der Ladeschale |
| Filament 1,75 mm, 32 mm lang | 1 | 1 | – | Scharnierstift Notrufklappe |

## Verbrauchsmaterial

| Teil | Menge | ca. € |
|---|---|---|
| PETG (Gehäuse, Schale, Kappen) | ca. 450 g (Hybrid ca. 500 g) | 12 |
| TPU 95A (Hörmuschel) | Rest, < 5 g | – |
| Litze 0,14 mm² (AWG 26), mehrere Farben | ca. 3 m | 3 |
| Schrumpfschlauch, Kabelbinder 2,5 mm, doppelseitige Klebepads | – | 4 |
| 2K-Epoxid (Hörerkopf, Magnete, Scheiben), Sekundenkleber mit Primer (TPU) | – | 6 |

## Summen (Schätzung)

| | Festnetz | Hybrid |
|---|---|---|
| Elektronik, Audio, Bedienung | ca. 95–115 € | ca. 210–240 € |
| Strom, Ladekontakte, Ladeschale | ca. 55–70 € | ca. 65–80 € |
| Mechanik, Verbrauchsmaterial | ca. 25–30 € | ca. 25–30 € |
| **Gesamt** | **ca. 175–215 €** | **ca. 300–350 €** zzgl. SIM-Vertrag |
