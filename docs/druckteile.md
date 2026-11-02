# Omafon – Druckteile und Zusammenbau

Alle Teile sind parametrisch in OpenSCAD (`cad/`). Die CI rendert bei jedem Push
das **komplette Druckpaket** als Artefakt `omafon-stl`. Die STL-Dateien liegen dort
schon in Druckrichtung:

```
tasten/einfarbig/            17 Tastenkappen (Farbwechsel oder einfarbig)
tasten/zweifarbig/           dieselben Kappen als *_kappe.stl + *_zeichen.stl (Mehrmaterial)
gehaeuse/festnetz/           Handteil 94 x 210 x 30 mm
gehaeuse/hybrid/             Handteil 94 x 210 x 36 mm (Platz für den SIM7600-HAT)
                             (Hörerkopf + Muschel stehen 21 mm über der Vorderseite)
ladeschale/festnetz/         Ladeschale passend zum 30-mm-Handteil
ladeschale/hybrid/           Ladeschale passend zum 36-mm-Handteil
```

![Handteil von vorn](../cad/gehaeuse_vorschau_vorn.png)
![Handteil von hinten: Notrufklappe, Akkudeckel, Lautsprecher, Kodiernut, Ladekontakte](../cad/gehaeuse_vorschau_hinten.png)

> **Stand:** Die Geometrie ist am Rechner geprüft: Kollisionen im Zusammenbau
> (auch mit gedrückten Tasten und der Elektronik als Platzhalter), Überhänge,
> Druckrichtung und fehlerfreies Rendern. **Gedruckt und anprobiert ist noch nichts.**
>
> **Reihenfolge:** 1. `pruefstueck.stl` (ca. 20 min) → Taster müssen fest
> einrasten, Einsatz einschmelzen, Lautstärketaste probestecken. 2. Eine Tastenkappe
> auf einen Taster. 3. Erst dann Deckel und Wanne.

## Teileliste

### Handteil (`gehaeuse/<variante>/`)

| Datei | Stück | Farbe (Vorschlag) | Druck | Hinweise |
|---|---|---|---|---|
| `pruefstueck.stl` | 1 | beliebig | flach | **zuerst drucken:** 2 Taster-Ausschnitte wie im Deckel, Dom für einen Einsatz, Loch der Lautstärketaste |
| `deckel.stl` | 1 | **dunkelgrau/schwarz** (Kontrast zu den weißen Kappen) | Vorderseite unten, ohne Stützen, **0,2 mm Schicht** | mit eingebauter Schalterplatte: 16 Taster klipsen von vorn ein (Platte 1,6 mm = 8 Lagen à 0,2 mm). Hörer mit Ringmulde, LED-Loch, Mikrofon |
| `hoererkopf.stl` | 1 | hell (sichtbare LED) | Oberseite unten, ohne Stützen | erhöhtes Kopfteil über den Tasten (18 mm): Ohr und Muschel liegen **gut 3 mm höher als die höchste Tastenkappe**, die Wange drückt beim Telefonieren keine Taste. Enthält Schallrohr und LED-Lichtrohr; wird auf den Deckel geklebt |
| `hoermuschel.stl` | 1 | **dunkel, TPU 95A** (sonst PETG) | flache Seite unten | weicher Ring (3 mm) oben auf dem Hörerkopf: führt das Ohr an die richtige Stelle und dichtet ab |
| `wanne.stl` | 1 | hellgrau/weiß | Rückseite unten, ohne Stützen, **0,2 mm Schicht** | Notrufmulde mit Schalterplatte 1,6 mm, Akkufach, Ladekontakte, Kodiernut |
| `tastengitter.stl` | 1 | wie Deckel | flach | **optional:** 1,2 mm hohe Taststege zwischen den Tasten, auf den Deckel kleben. Niedrig genug, dass gedrückte Kappen nicht anstoßen |
| `akkudeckel.stl` | 1 | wie Wanne | Außenseite unten | 2 Senkschrauben in 2,2 mm dicken Polstern |
| `notrufklappe.stl` | 1 | **rot** | stehend auf der Scharnierkante, **Brim** | Noppen außen = „hier ist der Notruf“; leichte Raste seitlich, Scharnier oben – fällt in der Schale und in der Hand von selbst zu |
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


## Druckeinstellungen

- **Material:** PETG (zäher als PLA, verträgt Wärme in der Hand und am Fenster).
  Tastenkappen gehen auch in PLA.
- **Bettgröße:** Handteil ist 210 mm lang. Das passt auf Drucker ab 220 × 220 mm
  bzw. auf 250 × 210 mm längs.
- Schicht **0,2 mm** für Deckel und Wanne (auch die erste Lage): die Schalterplatten
  sind auf 1,6 mm = 8 Lagen ausgelegt. Andere Schichthöhen ergeben 1,4/1,8 mm, dann
  halten die Taster nicht sicher. Ladeschale 0,2 mm, Kappen 0,12–0,16 mm.
- Löcher nicht per Slicer-Lochkompensation aufweiten, die Maße enthalten schon Spiel
  (Taster-Ausschnitt 14,1 mm, Teile 0,3 mm je Seite).
- 3–4 Wände, 20–25 % Füllung (Gyroid), Ladeschale 30 %.
- Keine Stützen außer der Brim an der Notrufklappe.

## Kaufteile für die Mechanik

| Teil | Stück | Wo |
|---|---|---|
| Gewindeeinsatz M2,5 × 3,5 (Einschmelzmutter, Ø 3,6 mm Loch) | 6 (+1 Prüfstück) | 4 im Deckel, 2 in den Akkudeckel-Domen |
| Zylinderschraube M2,5 × **25** (Festnetz) bzw. × **30** (Hybrid) | 4 | Gehäuse, von hinten (Senkung so tief, dass 3 mm im Einsatz greifen) |
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

Elektronik siehe [stueckliste.md](stueckliste.md), Anschlüsse in
[verkabelung.md](verkabelung.md).

## Zusammenbau Handteil

1. **Einsätze** mit dem Lötkolben (ca. 220 °C) einschmelzen: 4 in die Dome des
   Deckels, 2 von außen in die Akkudeckel-Dome der Wanne.
2. **Taster:** 16 Taster von vorn in den Deckel klipsen (sie rasten in der 1,6-mm-
   Platte ein). Optional das Tastengitter vorn aufkleben. Kappen erst ganz am
   Schluss aufstecken.
3. Hörkapsel, Mikrofon (mit Dichtring/Filz) und LED in die Halter im Deckel kleben.
   LED von unten ins Lichtrohr des Hörerkopfs stecken (Kopf schaut oben heraus,
   Beine verlängern), Drähte durch das LED-Loch im Deckel. Hörerkopf mit 2K-Kleber
   auf den Deckel kleben; der Stummel des Schallrohrs zentriert ihn in der
   Ringmulde über dem Hörer. Hörmuschel oben in die Mulde des Kopfs kleben.
   Hybrid: GNSS-Antenne in den Rahmen oben rechts.
4. **Wanne:** Notruftaster von außen in die Mulde klipsen, Notrufkappe aufstecken.
   Reedkontakt in den Kanal neben der Mulde schieben, Magnet in die Klappe kleben
   (Tasche innen, Seite zum Reedkontakt), Klappe mit dem Filamentstift einhängen.
   Stift an beiden Enden kurz anschmelzen. Die Klappe rastet seitlich leicht ein.
5. Messingscheiben in die Unterkante kleben, Litzen durch die Löcher (von links:
   +5 V, GND, GND, LS+, LS−). Stahlscheiben daneben einkleben.
6. Lautsprecher in den Ring über dem Gitter kleben. Lautstärketasten von innen
   einsetzen, Lochraster-Platinen mit den 6×6-Tastern in die Schienen schieben.
7. Pi auf die Abstandshalter schrauben (Hybrid: HAT aufstecken,
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

1. Nichts davon ist gedruckt. Toleranzen (Spiel 0,3 mm, Taster-Ausschnitt 14,1 mm,
   Kappenstößel) mit dem Prüfstück und einer Kappe am eigenen Drucker prüfen.
   Anpassbar über `spalt`, `mx_ausschnitt` (Gehäuse) und `stem_spiel` (Kappen).
2. Das Handteil ist mit 94 × 210 mm groß. Das folgt aus dem 24-mm-Raster der Tasten.
   Kleiner geht nur mit engerem Raster (`raster` in `omafon_tasten.scad`).
   Schwerer zu treffen, aber leichter in der Hand. Gewicht geschätzt 250–350 g.
3. Akkumaße sind Beispiele (3000 mAh 60 × 75 × 10, 5000 mAh 60 × 70 × 12). Den
   echten Akku nachmessen und `AK` anpassen.
4. Der Notruf sitzt hinten (wie bei Seniorenhandys üblich). Liegt das Telefon auf
   dem Rücken, muss Oma es erst anheben. In der Schale ist die Klappe von hinten
   oben erreichbar. Mit ihr ausprobieren.
