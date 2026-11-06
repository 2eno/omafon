# CLAUDE.md – Omafon

## Projektüberblick

Omafon ist ein sprechendes Telefon für Menschen mit starker Sehbehinderung.
Jeder Tastendruck wird angesagt, Anrufer werden mit Namen angekündigt, SMS werden per
Gong gemeldet und auf Tastendruck vorgelesen, SMS können diktiert werden, und ein
Notrufknopf ruft eine Kette von Kontakten an.

- Zwei Varianten: **Festnetz** (Fritz!Box per WLAN/SIP, `backend: sip`) und
  **Hybrid** (zusätzlich LTE-Modem für unterwegs, `backend: hybrid`). Ein reines
  Handy gibt es nicht mehr; `modem.py` ist nur noch der Mobilfunkteil des Hybrids.
- Hardware: Raspberry Pi Zero 2 W, MCP23017 (Ziffernblock per I²C), TPA2016
  (Verstärker), MAX17048 (Akku), CM108-Soundkarte, Ladeschale; Hybrid zusätzlich
  Waveshare SIM7600E-H 4G HAT. Stückliste/Verkabelung: `docs/stueckliste.md`,
  `docs/verkabelung.md`.
- Software: Python 3 (asyncio), eine Ereignis-Warteschlange, ein Zustandsautomat.
- Sprachausgabe: Piper (Fallback espeak-ng), feste Ansagen vorab gerendert.
- Spracherkennung: Vosk offline, optional eigener Whisper-Server.
- Gehäuseteile: OpenSCAD (`cad/`).

Status: Software im Simulator getestet, Hardware ungetestet.

## Modulübersicht

| Datei | Aufgabe |
|---|---|
| `omafon/main.py` | Start, systemd-Watchdog, PC-Simulator (`--sim`) |
| `omafon/phone.py` | Zustandsautomat (Wählen, Anrufe, SMS, Diktat, Notruf); `P`-Dict mit allen festen Ansagen |
| `omafon/telephony.py` | Schnittstelle `TelephonyBackend`, `create_backend()` (config `backend: sip \| hybrid`) |
| `omafon/modem.py` | Mobilfunkteil des Hybrids: AT-Treiber SIM7600, URC-Auswertung; `SimModem` für Tests |
| `omafon/sip.py` | Backend `sip`: baresip über ctrl_tcp, Fritz!Box-AB und -Telefonbuch, Verbindungsüberwachung |
| `omafon/sipsim.py` | `FakeBaresip` (ctrl_tcp-Server), `SipSimulator`, `LogNotifier` für Tests und `--sim` |
| `omafon/hybrid.py` | Backend `hybrid`: Fritz!Box + Mobilfunk gleichzeitig, Routing, Sparmodus; `HybridSimulator` |
| `omafon/fritz.py` | TR-064 (fritzconnection), XML-Parser, `SimFritzBox` |
| `omafon/notify.py` | Telegram/E-Mail als SMS-Ersatz (Notruf-Hinweis, Diktat), standardmäßig aus |
| `omafon/pdu.py` | SMS im PDU-Modus (GSM-7, UCS-2, lange SMS) |
| `omafon/audio.py` | Piper mit WAV-Cache, Töne, TPA2016-Ansteuerung; `SimAudio` |
| `omafon/stt.py` | Vosk (Namen mit Grammatik, Diktat), optional Whisper; `SimRecognizer` |
| `omafon/hardware.py` | Tastenabfrage 100 Hz, Entprellung (`KeyTracker`), Akku, Vibration; `SimHardware` |
| `omafon/numbers.py` | Ziffernwörter ("zwo"), Nummern in Gruppen, Uhrzeit/Datum |
| `omafon/config.py` | `config.yaml` laden, Kontakte, Notrufkette |
| `omafon/admin.py` | Verwaltung für die Android-App: HTTPS+JSON `/api/v1`, Koppeln per Code, Einstellungs-Schema `SETTINGS`, Kontakte |
| `omafon/update.py` | Signierte Updates (Ed25519), A/B unter `<data_dir>/releases`, Rückfall nach `MAX_BOOTS` Fehlstarts |
| `tools/prerender.py` | Alle festen Ansagen vorab als WAV erzeugen |
| `tools/make_release.py` | Update-Schlüssel erzeugen, signiertes Paket + `manifest.json` bauen |
| `tools/api_fixtures.py` | JSON-Beispiele der Schnittstelle für die App-Tests (`android/app/src/test/resources/api/`) |
| `android/` | Companion-App (Kotlin, Compose, Material 3): `data/` API, Pinning, Speicher, mDNS; `ui/` Bildschirme |
| `systemd/omafon-start.sh`, `systemd/omafon.avahi.xml` | Start-Wrapper (aktive Version), mDNS-Dienst `_omafon._tcp` |
| `tests/test_omafon.py` | Kern-Tests (Tasten, Anrufe, SMS, Notruf) mit SimModem ohne Hardware |
| `tests/test_festnetz.py` | SIP-Backend gegen FakeBaresip, Fritz!Box, Ladeschale |
| `tests/test_hybrid.py` | Hybrid-Routing, Notruf, Zweitanruf, Sparmodus |
| `tests/test_admin.py` | Koppeln, Einstellungen, Neustart nur in Ruhe, HTTPS, Updates/Rückfall, App-Fixtures aktuell |
| `cad/omafon_masse.scad` | Gemeinsame Maße Handteil/Ladeschale je `variante` (festnetz 30 mm, hybrid 36 mm dick) |
| `cad/omafon_gehaeuse.scad` | Handteil-Gehäuse: pruefstueck, deckel (mit Schalterplatte), wanne, tastengitter, akkudeckel, notrufklappe, lautstaerke_*, hoererkopf, hoermuschel; STL in Druckrichtung |
| `cad/omafon_ladeschale.scad` | Ladeschale mit Lautsprecher, Federkontakten, Kodierrippe |
| `docs/druckteile.md` | Teileliste, Druckeinstellungen, Kaufteile, Zusammenbau (liegt auch im STL-Paket) |
| `config.festnetz.example.yaml`, `config.hybrid.example.yaml` | Beispielkonfigurationen (nur Platzhalter) |
| `docs/stueckliste.md`, `docs/verkabelung.md` | Stückliste mit Preisen, Verkabelung/Pinbelegung beider Varianten |
| `cad/omafon_tasten.scad` | Tastenkappen und Tastenfront, parametrisch |
| `systemd/omafon.service` | Dienst mit Watchdog |

## Befehle

```bash
pip install -r requirements-dev.txt                       # PyYAML, cryptography
python3 -m unittest discover -s tests -v                  # Tests
python3 -m omafon.main --config config.festnetz.example.yaml --sim  # Festnetz-Simulator (Daten in ./sim-data)
python3 -m omafon.main --config config.hybrid.example.yaml --sim    # Hybrid-Simulator
sudo -u omafon python3 -m tools.prerender /etc/omafon/config.yaml  # Ansagen vorab rendern (Pi)
python3 -m omafon.main --config config.festnetz.example.yaml --sim --admin --admin-port 8443  # Simulator mit App-Schnittstelle
python3 -m tools.api_fixtures                             # JSON-Beispiele für die App erneuern
(cd android && ./gradlew testDebugUnitTest assembleDebug)  # App testen und bauen
openscad -D 'teil="ziffer"' -D 'ziffer="5"' -o taste_5.stl cad/omafon_tasten.scad
openscad -D 'teil="ziffer"' -D 'ziffer="5"' -D 'farbteil="zeichen"' -o taste_5_zeichen.stl cad/omafon_tasten.scad
openscad -D 'variante="hybrid"' -D 'teil="wanne"' -o wanne.stl cad/omafon_gehaeuse.scad
```

Im Simulator: Tasten `0-9 * #`, `a` Anrufen, `h` Auflegen, `m` Nachricht, `i` Info,
`L<taste>` lang drücken, `sos` Notruf; Netz: `!ring <nr>`, `!sms <nr> <text>`, `!sag <text>`.

## Regeln

1. **Tastendruck → Ansage muss sofort kommen.** Ziffern werden schon beim
   `down`-Ereignis angesagt. Event-Handler blockieren nie; lange Abläufe laufen als
   Job (`start_job`), kurze Ansagen über `speak()`. Keine Synthese, kein I/O und kein
   `await` auf langsame Dinge im Weg zwischen Tastendruck und Ansage.
2. **Notruf darf nie von I²C abhängen.** SOS-Knopf und Klappe hängen direkt an
   Pi-GPIOs (`PI_INPUTS`) und werden auch abgefragt, wenn der MCP23017 ausfällt.
   Ein ausgefallener Verstärker (TPA2016) darf den Notruf nicht verhindern.
3. **Ansagetexte nur im `P`-Dict in `omafon/phone.py` ändern.** Feste Ansagen mit
   Platzhaltern (z. B. `f"Anruf von {name}."`) zusätzlich in `fixed_phrases()`
   aufnehmen – nur diese Liste liegt dauerhaft im Cache. `tools/prerender.py`
   rendert sie vorab, das Telefon rendert Fehlendes auch selbst im Leerlauf nach.
4. Tests müssen ohne Hardware laufen: Hardware-Bibliotheken (`serial`, `smbus2`,
   `gpiozero`, `vosk`) nur lokal in Funktionen importieren.
5. **Nachrichten nie automatisch vorlesen.** Neue SMS nur per Gong (wiederholt alle
   `news_signal_minutes`) und blinkender LED ankündigen; vorgelesen wird erst auf
   Tastendruck. Kein Gong im Gespräch, in Menüs oder in der Ruhezeit.
6. **Tasten gut lesbar halten:** Zeichen immer in Kontrastfarbe zur Kappe
   (`FARBEN` in der SCAD-Datei), Kappe und Zeichen als getrennte Körper (`farbteil`).
   **Maße von Handteil und Ladeschale nur in `cad/omafon_masse.scad`** ändern, sonst
   passt das Telefon nicht mehr in die Schale. CAD-Teile müssen ohne OpenSCAD-Warnung
   rendern (CI bricht sonst ab), STL-Ausgabe immer in Druckrichtung ohne Stützen.
   Schalterplatten 1,6 mm (8 Lagen à 0,2 mm), Taster-Ausschnitt 14,1 mm, Spiel 0,3 mm.
   **Ohr vor Tasten:** Hörerkopf + Muschel müssen höher stehen als jede Tastenkappe,
   und im Gespräch legt die Auflegetaste nur gehalten auf (`hangup_hold_s`) – sonst
   legt die Wange auf.
7. **Phone spricht nur über `TelephonyBackend`.** Neue Netzfunktionen als Methode/
   Ereignis im Backend, nie Backend-Sonderfälle in `phone.py`. Optionale Fähigkeiten
   (`supports_sms`, `online`, `status_words`) haben sichere Standardwerte.
8. **Festnetz: Verbindung weg ist nie stumm.** `link_lost` wird angesagt und wiederholt;
   Wählen ohne Verbindung sagt das sofort. Das Backend baut selbst wieder auf.
9. **Anrufernamen nur aus Kontakten und dem Fritz!Box-Telefonbuch**, nie aus dem
   SIP-Anzeigenamen (vom Anrufer frei wählbar → Betrugsgefahr).
10. **Hybrid: Notruf hat immer einen zweiten Weg.** Scheitert ein Weg, sofort den
    anderen; 110/112 über Mobilfunk auch ohne eigenes Netz. „Kein Netz“ erst, wenn
    beide Wege fehlen. Zweitanrufe auf dem anderen Weg abweisen, nie anklopfen.
11. Keine echten Telefonnummern, Standorte oder Zugangsdaten committen.
   `config.yaml` ist in `.gitignore`; Beispiele gehören in `config.festnetz.example.yaml`
   bzw. `config.hybrid.example.yaml`, Kennwörter dort nur als `PLATZHALTER_…`.
12. **Pinbelegung nur gemeinsam ändern:** GPIO-/MCP-Belegung steht in
   `omafon/hardware.py` und `docs/verkabelung.md` – immer beide anpassen.
13. **Companion-App:** Die Schnittstelle in `omafon/admin.py` ist der Vertrag. Bei
   Änderungen `python3 -m tools.api_fixtures` laufen lassen und die Kotlin-Modelle in
   `android/.../data/Models.kt` anpassen. Neue Einstellungen nur in `SETTINGS` eintragen
   (die App zeigt sie generisch an). Kennwörter nie an die App zurückgeben,
   `update_public_key` nie über die App änderbar machen. Neustarts nach Änderungen
   nur über `phone.request_restart()` – das wartet, bis das Telefon in Ruhe ist.
14. **Einstellungen der App liegen in `<data_dir>/config.yaml`** (`/etc` ist schreibgeschützt);
   diese Datei hat Vorrang vor `/etc/omafon/config.yaml`.
