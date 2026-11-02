# Omafon – Druckteile und Zusammenbau

Alle Teile sind parametrisch in OpenSCAD (`cad/`). Die CI rendert bei jedem Push
das **komplette Druckpaket** als Artefakt `omafon-stl`. Die STL-Dateien liegen dort
schon in Druckrichtung:

```
tasten/einfarbig/            17 Tastenkappen (Farbwechsel oder einfarbig)
tasten/zweifarbig/           dieselben Kappen als *_kappe.stl + *_zeichen.stl (Mehrmaterial)
gehaeuse/festnetz/           Handteil 94 x 210 x 30 mm
gehaeuse/mobil_hybrid/       Handteil 94 x 210 x 36 mm (Platz für den SIM7600-HAT)
ladeschale/festnetz/         Ladeschale passend zum 30-mm-Handteil
ladeschale/mobil_hybrid/     Ladeschale passend zum 36-mm-Handteil
```

![Handteil von vorn](../cad/gehaeuse_vorschau_vorn.png)
![Handteil von hinten: Notrufklappe, Akkudeckel, Lautsprecher, Kodiernut, Ladekontakte](../cad/gehaeuse_vorschau_hinten.png)

> **Stand:** Die Geometrie ist am Rechner geprüft (Kollisionen, Schnitte,
> Druckrichtung, fehlerfreies Rendern). **Gedruckt und anprobiert ist noch nichts.**
> Erst eine Taste, die Tastenplatte und den Deckel drucken und anprobieren, dann
> den Rest.

## Teileliste

### Handteil (`gehaeuse/<variante>/`)

| Datei | Stück | Farbe (Vorschlag) | Druck | Hinweise |
|---|---|---|---|---|
| `deckel.stl` | 1 | hellgrau/weiß | Vorderseite unten, ohne Stützen | Fenster, Hörer mit Ringmulde, LED, Mikrofon, 6 Rasthaken |
| `hoererkopf.stl` | 1 | wie Deckel | Oberseite unten, ohne Stützen | erhöhtes Kopfteil über den Tasten (15 mm): Ohr und Muschel liegen **höher als die Tastenkappen**, die Wange drückt beim Telefonieren keine Taste. Enthält Schallrohr und LED-Lichtrohr; wird auf den Deckel geklebt |
| `hoermuschel.stl` | 1 | **dunkel, TPU 95A** (sonst PETG) | flache Seite unten | weicher Ring (3 mm) oben auf dem Hörerkopf: führt das Ohr an die richtige Stelle und dichtet ab |
| `wanne.stl` | 1 | hellgrau/weiß | Rückseite unten, ohne Stützen | Notrufmulde (Brücke über 21 mm), Akkufach, Ladekontakte |
| `tastenplatte.stl` | 1 | **schwarz** | Platte unten | dunkle Platte = Kontrast zu den weißen Kappen; **1,5 mm** an den Ausschnitten nicht verändern (Cherry-MX-Klemmmaß) |
| `akkudeckel.stl` | 1 | wie Wanne | Außenseite unten | 2 Senkschrauben |
| `notrufklappe.stl` | 1 | **rot** | stehend auf der Scharnierkante, Brim | Noppen außen = „hier ist der Notruf“ |
| `lautstaerke_plus.stl` | 1 | dunkel | Kragen unten | erhabenes Kreuz |
| `lautstaerke_minus.stl` | 1 | dunkel | Kragen unten | erhabener Balken |

### Tastenkappen (`tasten/`)

17 Stück: Ziffern 0–9, Stern, Raute (weiß, Zeichen schwarz), Anrufen (gelb, Zeichen
schwarz), Auflegen (schwarz, Zeichen weiß), Nachricht und Info (weiß, Zeichen
schwarz), Notruf (rot, Noppen weiß). Druck mit 0,12–0,16 mm Schicht, Oberseite
oben. Details und Farbwahl: Kommentar in `cad/omafon_tasten.scad`.

### Ladeschale (`ladeschale/<variante>/`)

| Datei | Stück | Farbe | Druck | Hinweise |
|---|---|---|---|---|
| `schale.stl` | 1 | dunkel | Öffnung oben, ohne Stützen | Schacht, Trichter, Kodierrippe, Grill, USB-C-Halter |
| `boden.stl` | 1 | beliebig | flach | Gewichtskammer, Gummifüße |
| `kontakttraeger.stl` | 1 | beliebig | flach | 5 Federkontakte, 2 Magnete |

Mobil- und Hybridgerät haben dieselben Maße; `mobil_hybrid` passt für beide.

## Druckeinstellungen

- **Material:** PETG (zäher als PLA, verträgt Wärme in der Hand und am Fenster).
  Tastenkappen gehen auch in PLA.
- **Bettgröße:** Handteil ist 210 mm lang. Das passt auf Drucker ab 220 × 220 mm
  bzw. auf 250 × 210 mm längs.
- Schicht 0,2 mm (Gehäuse, Schale), 0,12–0,16 mm (Kappen, Tastenplatte).
- 3–4 Wände, 20–25 % Füllung (Gyroid), Ladeschale 30 %.
- Keine Stützen außer der Brim an der Notrufklappe.

## Kaufteile für die Mechanik

| Teil | Stück | Wo |
|---|---|---|
| Gewindeeinsatz M2,5 × 3,5 (Einschmelzmutter, Ø 3,6 mm Loch) | 6 | 4 im Deckel, 2 in den Akkudeckel-Domen |
| Zylinderschraube M2,5 × **25** (Festnetz) bzw. × **30** (Mobil/Hybrid) | 4 | Gehäuse, von hinten |
| Senkschraube M2,5 × 6 | 2 | Akkudeckel |
| Schraube M2,5 × 6 (selbstformend) oder Abstandsbolzen | 4 | Pi Zero 2 W |
| Filament 1,75 mm, 32 mm lang | 1 | Scharnierstift Notrufklappe |
| Magnet 5 × 1 mm + Reedkontakt (Glas, 2 × 14 mm) oder Hallschalter | je 1 | Klappenschalter (GPIO 23) |
| Taster im Cherry-MX-Format | 17 | 16 Tasten + Notruf |
| Kurzhubtaster 6 × 6 mm + Lochraster 14 × 16 mm | je 2 | Lautstärke |
| Messingscheibe Ø 5 × 1 mm | 5 | Ladekontakte am Handteil |
| Stahlscheibe Ø 8 × 1,5 mm | 2 | Gegenstück zu den Magneten der Schale |
| Federkontakt (Pogo-Pin) Ø 2 mm, Magnet 8 × 3 mm | 5 / 2 | Ladeschale |
| Gummifüße Ø 10, Stahlscheiben 150–250 g, M3 × 8 | 4 / – / 2 | Ladeschale |

Elektronik siehe [festnetz-hardware.md](festnetz-hardware.md) bzw.
[hybrid.md](hybrid.md).

## Zusammenbau Handteil

1. **Einsätze** mit dem Lötkolben (ca. 220 °C) einschmelzen: 4 in die Dome des
   Deckels, 2 von außen in die Akkudeckel-Dome der Wanne.
2. **Tastenplatte:** 16 Taster von vorn einklipsen. Die Platte von innen ins
   Deckelfenster schieben, bis die 6 Rasthaken einrasten. Die Taststege schauen
   0,8 mm aus dem Fenster. Kappen erst ganz am Schluss aufstecken.
3. Hörkapsel, Mikrofon (mit Dichtring/Filz) und LED in die Halter im Deckel kleben.
   LED von unten ins Lichtrohr des Hörerkopfs stecken (Kopf schaut oben heraus,
   Beine verlängern), Drähte durch das LED-Loch im Deckel. Hörerkopf mit 2K-Kleber
   auf den Deckel kleben; der Stummel des Schallrohrs zentriert ihn in der
   Ringmulde über dem Hörer. Hörmuschel oben in die Mulde des Kopfs kleben.
   Mobil/Hybrid: GNSS-Antenne in den Rahmen oben rechts.
4. **Wanne:** Notruftaster von außen in die Mulde klipsen, Notrufkappe aufstecken.
   Reedkontakt in den Kanal neben der Mulde schieben, Magnet in die Klappe kleben,
   Klappe mit dem Filamentstift einhängen. Stift an beiden Enden kurz anschmelzen.
5. Messingscheiben in die Unterkante kleben, Litzen durch die Löcher (von links:
   +5 V, GND, GND, LS+, LS−). Stahlscheiben daneben einkleben.
6. Lautsprecher in den Ring über dem Gitter kleben. Lautstärketasten von innen
   einsetzen, Lochraster-Platinen mit den 6×6-Tastern in die Schienen schieben.
7. Pi auf die Abstandshalter schrauben (Mobil/Hybrid: HAT aufstecken,
   Schaumstoffpad zum Akku). Kleine Platinen mit Klebepads und Kabelbindern ins
   Feld rechts neben dem Akku.
8. Akku einlegen, Akkudeckel mit 2 Senkschrauben schließen.
9. Deckel aufsetzen (Falz zentriert), 4 Schrauben von hinten. Tastenkappen
   aufstecken.

## Zusammenbau Ladeschale

1. Federkontakte in den Kontaktträger pressen (Markierung = Kontakt 1, +5 V),
   Magnete einkleben (Polung so, dass sie die Stahlscheiben anziehen).
2. Kontaktträger in die Tasche am Schachtboden kleben.
3. Lautsprecher von unten an den Grill kleben, USB-C-Platine in die Nut schieben.
4. Stahlscheiben in die Gewichtskammer des Bodens kleben, Boden mit 2 × M3
   anschrauben, Gummifüße aufkleben.

## Anpassen

- Gemeinsame Maße von Handteil und Schale (Breite, Länge, Dicke je Variante,
  Kontakte, Kodierung) stehen in **`cad/omafon_masse.scad`**. Wer dort etwas ändert,
  muss Gehäuse **und** Schale neu exportieren.
- Einbauteile (Hörkapsel, Mikrofon, Lautsprecher, Akku, Einsätze) sind oben in
  `cad/omafon_gehaeuse.scad` einstellbar, z. B.
  `openscad -D 'variante="hybrid"' -D 'teil="wanne"' -D 'ls_d=31.6' …`.
- Kappe zu stramm auf dem Taster: `stem_spiel` in `omafon_tasten.scad`.

## Offene Punkte

1. Nichts davon ist gedruckt. Toleranzen (Falz 0,2 mm, Fenster 0,4 mm, Rasthaken)
   am eigenen Drucker prüfen.
2. Das Handteil ist mit 94 × 210 mm groß. Das folgt aus dem 24-mm-Raster der Tasten.
   Kleiner geht nur mit engerem Raster (`raster` in `omafon_tasten.scad`).
   Schwerer zu treffen, aber leichter in der Hand. Gewicht geschätzt 250–350 g.
3. Akkumaße sind Beispiele (3000 mAh 60 × 75 × 10, 5000 mAh 60 × 70 × 12). Den
   echten Akku nachmessen und `AK` anpassen.
4. Der Notruf sitzt hinten (wie bei Seniorenhandys üblich). Liegt das Telefon auf
   dem Rücken, muss Oma es erst anheben. In der Schale ist die Klappe von hinten
   oben erreichbar. Mit ihr ausprobieren.
