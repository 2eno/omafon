# Hybridgerät: zu Hause Festnetz, unterwegs Handy

Ein Omafon, das **zu Hause** als schnurloses Telefon an der Fritz!Box arbeitet
(WLAN/SIP, Festnetznummer, Anrufbeantworter, Ladeschale) und **unterwegs** als Handy
(LTE, Handynummer, SMS, GPS). Für die Person gibt es **ein** Gerät mit **einer**
Bedienung. Welcher Weg gerade telefoniert, entscheidet das Gerät selbst.

`backend: hybrid` – Code in `omafon/hybrid.py`, Beispiel in
`config.hybrid.example.yaml`, Tests in `tests/test_hybrid.py`.
Ausprobieren ohne Hardware:

```bash
python3 -m omafon.main --config config.hybrid.example.yaml --sim
# !wlan aus/an = Wohnung verlassen/betreten   !netz aus/an = Funkloch
# !ring = Festnetz (zu Hause)   !mring = Handynummer   !sms = SMS   !ab = Anrufbeantworter
```

## 1. Warum hybrid?

| Situation | nur Festnetz | nur Mobilfunk | **Hybrid** |
|---|---|---|---|
| Zu Hause, normaler Anruf | ✔ Festnetz, AB | ✔ (Empfang im Haus?) | ✔ über Fritz!Box |
| Garten, Wohnungsrand | WLAN bricht ab | ✔ | ✔ schaltet bei schwachem WLAN auf Mobilfunk |
| Einkaufen, Arzt, Familie besuchen | ✘ | ✔ | ✔ |
| Stromausfall / Fritz!Box hängt | ✘ | ✔ | ✔ automatisch Mobilfunk |
| Funkloch im Haus (Keller, dicke Wände) | ✔ | ✘ | ✔ |
| Notruf zu Hause | ✔ Anschlussadresse | GPS drinnen oft schlecht | ✔ Festnetz zuerst, Mobilfunk als Rückfall |
| Notruf unterwegs | ✘ | ✔ GPS per SMS | ✔ |

Hauptgewinn ist **Ausfallsicherheit**: Für einen Notruf stehen zwei unabhängige
Wege bereit.

## 2. Verhalten (Entscheidungstabelle)

| Ereignis | Regel | Warum |
|---|---|---|
| Normaler Anruf, zu Hause | Fritz!Box, bei Fehler sofort Mobilfunk | Festnetz-Flatrate, gute Sprachqualität im Haus |
| Normaler Anruf, WLAN schwächer als −75 dBm | Mobilfunk zuerst | Gespräch würde am WLAN-Rand abreißen |
| Normaler Anruf, unterwegs | Mobilfunk | – |
| **110/112**, zu Hause | Festnetz zuerst, dann Mobilfunk | Anbieter übermittelt die Anschlussadresse |
| **110/112**, unterwegs/Funkloch | Mobilfunk, **auch ohne eigenes Netz** | Notruf geht über jedes verfügbare Netz |
| Klingeln auf einem Weg | dieses Gespräch gehört dem Weg | – |
| Klingeln auf dem anderen Weg während eines Gesprächs | **abweisen** (Anrufer hört besetzt bzw. landet auf der Mailbox/dem AB) | Anklopfen ohne Display ist für die Zielgruppe zu verwirrend |
| SMS | über Mobilfunk; ohne Netz Push (Telegram/E-Mail), wenn eingerichtet | – |
| AB-Nachricht (Fritz!Box) und SMS | ein gemeinsamer Posteingang, gleiche Ankündigung (Gong, LED) | eine Bedienung |
| Notruf-Hinweis | SMS an die Notfallkontakte; zu Hause mit `home_position`, unterwegs mit GPS-Link | – |
| Fritz!Box weg, Mobilfunk da | **keine** Ansage (optional „Unterwegs …“ mit `announce_mode`) | unterwegs ist das der Normalfall |
| Beide Wege weg | nach 10 s „Kein Netz. Telefonieren geht gerade nicht. Ich versuche es weiter.“, Erinnerung alle 10 min, nachts nur auf Tastendruck | nie ohne Rückmeldung |
| Info-Taste | „Zu Hause. Verbindung zur Fritzbox gut. Mobilfunk: Empfang gut.“ | Zustand jederzeit abfragbar |

Phone bleibt dabei unverändert bis auf eines: Das Backend darf bestimmen, welcher
Text aus dem P-Dict bei „keine Verbindung“ gesprochen wird.

## 3. Rufnummern – das muss die Familie wissen

Das Gerät hat **zwei Nummern**: Festnetz und Handy. Drei Betriebsarten:

| `home_modem` | Zu Hause erreichbar über | Akku | Einrichtung |
|---|---|---|---|
| `"on"` (Standard) | Festnetz **und** Handy | ca. 0,1 W mehr in Bereitschaft | keine |
| `"off"` (Sparmodus) | Festnetz; Handy-Anrufe nur mit Rufumleitung | Mobilfunk ruht (Flugmodus), wenn die Fritz!Box 5 min stabil ist | beim Mobilfunkanbieter **Rufumleitung „bei nicht erreichbar“ auf die Festnetznummer** (GSM-Code `**62*<Festnetznummer>#`) |
| *Ausbaustufe* | Festnetz-Anrufe unterwegs aufs Handy | – | Fritz!Box-Rufumleitung per TR-064 beim Verlassen ein- und beim Heimkommen ausschalten (`X_AVM-DE_OnTel` kennt Rufumleitungen; nicht umgesetzt, Kosten der Umleitung beachten) |

Empfehlung: **`"on"`**. Der Sparmodus spart nur etwa 15 % der Bereitschaftsleistung
(der Pi braucht ca. 0,6 W, das Modem in Ruhe ca. 0,1 W). Dafür sind SMS zu Hause
verzögert, und ein Notruf über Mobilfunk muss das Modem erst wecken. Auch 112
braucht nach dem Einschalten einige Sekunden, bis eine Funkzelle gefunden ist;
normale Anrufe gehen erst nach der Netzanmeldung (bis ca. 45 s).
Der Code weckt das Modem automatisch für Notruf-SMS, Mobilfunk-Wählen und GPS.

Die Mailbox des Mobilfunkanbieters sollte **aus** sein oder auf den Festnetz-AB
umleiten. Omafon liest nur den AB der Fritz!Box vor.

## 4. Grenzen

- **Kein Weiterreichen im Gespräch.** Wer mit einem WLAN-Gespräch die Wohnung
  verlässt, verliert die Verbindung. Das Gerät sagt dann „Gespräch beendet“ wie bei
  jedem Abbruch. Ein Rückruf über Mobilfunk wäre machbar, wurde aber bewusst nicht
  automatisch umgesetzt (Doppelanrufe, Kosten) → offene Frage. Die
  WLAN-Schwelle (`weak_wifi_dbm`) verringert das Problem.
- **Zwei Absendernummern.** Wer angerufen wird, sieht je nach Weg die Festnetz-
  oder die Handynummer. Beide gehören in die Kontakte der Familie.
- **Anklopfen gibt es nicht.** Ein zweiter Anrufer auf dem anderen Weg wird
  abgewiesen.

## 5. Hardware

Grundlage ist die **Mobilfunk-Hardware** (SIM7600E-H) **plus Ladeschale** der
Festnetz-Variante. Details zu Schale, Kontakten und Relais:
[festnetz-hardware.md](festnetz-hardware.md).

### Abweichungen gegenüber Festnetz

| Teil | Hybrid | ca. € |
|---|---|---|
| Waveshare SIM7600E-H 4G HAT | Mobilfunk, GNSS | 90–100 |
| LTE-FPC-Antenne(n) zum Einkleben (Haupt, optional Diversity) | statt Stabantennen | 5–10 |
| Aktive GNSS-Keramikantenne 25 × 25 mm | GPS beim Notruf unterwegs | 5–8 |
| Aufwärtswandler 5 V **3 A** (statt 1 A) | Sendespitzen des Modems bis 2 A | 10–12 |
| LiPo **4000–5000 mAh** (statt 3000 mAh) | Bereitschaft | 15–20 |
| Nano-/Micro-SIM mit Sprachtarif | – | Vertrag |
| **Gesamt** | Festnetz-Handteil + diese Teile + Ladeschale | **ca. 270–320** |

### Strombilanz

| Zustand | Leistung (Schätzung) |
|---|---|
| Pi in Ruhe, WLAN verbunden | ca. 0,60 W |
| SIM7600 in Ruhe, eingebucht | ca. 0,10 W (mit Schlafmodus AT+CSCLK und DTR-Leitung weniger) |
| Rest (Verstärker aus, MCP23017, Akku-IC, LED) | ca. 0,03 W |
| **Summe Bereitschaft** | **ca. 0,73 W** (Sparmodus zu Hause: ca. 0,63 W) |

5000 mAh × 3,7 V × 85 % ≈ 15,7 Wh → **ca. 21 h Bereitschaft**
(3000 mAh: ca. 13 h). Das Telefon gehört weiterhin nachts in die Schale. Die
Akkuwarnungen bei 20/10/5 % kommen per Ansage.

### Antennen im Handteil

```
   ┌──────────────┐  oben:  GNSS-Patch (zum Himmel), WLAN-Platinenantenne des Pi
   │ GNSS    WLAN │         ≥ 20 mm Abstand zueinander
   │              │
   │   Tasten     │  Mitte: Tastenfeld, Pi, Modem-HAT
   │              │
   │  Akku (hinten)│ Akku nie über einer Antenne
   │ LTE-FPC      │  unten: LTE-Hauptantenne, möglichst weit weg vom Kopf
   └──────────────┘
```

- LTE unten, also beim Telefonieren am Kinn statt am Ohr: weniger Abstrahlung zum Kopf.
- Die Platinenantenne des Pi **nicht umbauen** (Funkzulassung, siehe
  [festnetz-recherche.md](festnetz-recherche.md#4-zulassung-funkanlagengesetz--red)).
- LTE-Band 7 (2,6 GHz) liegt nahe am WLAN (2,4 GHz). Abstand und Filter im Modem
  reichen in der Regel; bei Störungen im Test die LTE-Antenne weiter weg legen.

### Gehäuse und Ladeschale

- Das Handteil ist durch HAT und größeren Akku **6 mm dicker** (36 statt 30 mm).
  Gehäuse und Ladeschale nehmen das über `variante="hybrid"` aus
  `cad/omafon_masse.scad`. Das fertige Druckpaket liegt im CI-Artefakt unter
  `gehaeuse/hybrid/` und `ladeschale/hybrid/`. Teileliste und
  Zusammenbau: [druckteile.md](druckteile.md).
- Die SIM-Karte steckt im HAT über dem Pi. Zum Wechseln das Gehäuse öffnen
  (4 Schrauben hinten). Das ist selten nötig, und Oma muss da nie ran.

## 6. Offene Fragen

1. **SAR/Abstrahlung am Kopf:** Ein selbstgebautes LTE-Telefon ist nicht
   SAR-geprüft. Antenne unten, Lautstärke für Freisprechen gut. Gilt genauso für
   jedes selbstgebaute LTE-Gerät.
2. **Sparmodus oder nicht?** (Empfehlung „on“) und ob der Anbieter die
   Rufumleitung „bei nicht erreichbar“ zuverlässig ausführt.
3. **Automatischer Rückruf über Mobilfunk** nach einem WLAN-Abbruch im Gespräch:
   gewünscht?
4. **Fritz!Box-Rufumleitung unterwegs** (Festnetz → Handy per TR-064): gewünscht?
   Kostet je nach Tarif Gebühren.
5. **Welcher Weg bei schwachem WLAN, aber gutem Mobilfunk für den Notruf?** Umgesetzt
   ist Mobilfunk (stabile Verbindung vor Adressübermittlung). Alternative:
   Festnetz trotzdem zuerst.
6. Alle offenen Fragen aus [festnetz-recherche.md](festnetz-recherche.md#offene-fragen-auch-im-pull-request)
   gelten weiter (AB-Format, Notruf über IP-Telefon, baresip am Pi).
