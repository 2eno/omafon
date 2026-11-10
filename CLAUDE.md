# CLAUDE.md – Omafon

## Project overview

Omafon is a talking phone for people with severe visual impairment.
Every key press is announced, incoming calls and SMS are read aloud,
SMS can be dictated, and an emergency button calls a chain of contacts.

- Two variants: **landline** (Fritz!Box via Wi-Fi/SIP, `backend: sip`) and
  **hybrid** (additionally an LTE modem for on the go, `backend: hybrid`). There is
  no pure mobile phone any more; `modem.py` is only the cellular part of the hybrid.
- Hardware: Raspberry Pi Zero 2 W, MCP23017 (keypad via I²C), TPA2016
  (amplifier), MAX17048 (battery), CM108 sound card, charging cradle; the hybrid
  adds a Waveshare SIM7600E-H 4G HAT. Bill of materials/wiring: `docs/stueckliste.md`,
  `docs/verkabelung.md`.
- Software: Python 3 (asyncio), one event queue, one state machine.
- Speech output: Piper (fallback espeak-ng), fixed announcements pre-rendered.
- Speech recognition: Vosk offline, optionally your own Whisper server.
- Housing parts: OpenSCAD (`cad/`).

Status: software tested in the simulator, hardware untested.

**Language:** code, comments, logs and developer docs are English. Everything the
user hears or reads on the device (announcements in `P`, SMS/notification texts,
number words) stays **German**, as do the values in the example configs and the
OpenSCAD parameter names (`teil`, `variante`, `ziffer`, …). Every doc has a German
version `*.de.md`; keep both in sync.

## Module overview

| File | Purpose |
|---|---|
| `omafon/main.py` | Startup, systemd watchdog, PC simulator (`--sim`) |
| `omafon/phone.py` | State machine (dialling, calls, SMS, dictation, emergency call); `P` dict with all fixed announcements |
| `omafon/telephony.py` | Interface `TelephonyBackend`, `create_backend()` (config `backend: sip \| hybrid`) |
| `omafon/modem.py` | Cellular part of the hybrid: SIM7600 AT driver, URC parsing; `SimModem` for tests |
| `omafon/sip.py` | Backend `sip`: baresip via ctrl_tcp, Fritz!Box answering machine and phone book, connection monitoring |
| `omafon/sipsim.py` | `FakeBaresip` (ctrl_tcp server), `SipSimulator`, `LogNotifier` for tests and `--sim` |
| `omafon/hybrid.py` | Backend `hybrid`: Fritz!Box + cellular at the same time, routing, power saving; `HybridSimulator` |
| `omafon/fritz.py` | TR-064 (fritzconnection), XML parser, `SimFritzBox` |
| `omafon/notify.py` | Telegram/e-mail as an SMS substitute (emergency notice, dictation), off by default |
| `omafon/pdu.py` | SMS in PDU mode (GSM-7, UCS-2, long SMS) |
| `omafon/audio.py` | Piper with WAV cache, tones, TPA2016 control; `SimAudio` |
| `omafon/stt.py` | Vosk (names with grammar, dictation), optionally Whisper; `SimRecognizer` |
| `omafon/hardware.py` | Key polling at 100 Hz, debouncing (`KeyTracker`), battery, vibration; `SimHardware` |
| `omafon/numbers.py` | Digit words ("zwo"), numbers in groups, time/date |
| `omafon/config.py` | Load `config.yaml`, contacts, emergency chain |
| `tools/prerender.py` | Pre-render all fixed announcements as WAV |
| `tests/test_omafon.py` | Core tests (keys, calls, SMS, emergency call) with SimModem, no hardware; checks the wiring docs against `hardware.py` |
| `tests/test_festnetz.py` | SIP backend against FakeBaresip, Fritz!Box, charging cradle |
| `tests/test_hybrid.py` | Hybrid routing, emergency call, second call, power saving |
| `cad/omafon_masse.scad` | Shared dimensions of handset/cradle per `variante` (festnetz 30 mm, hybrid 36 mm thick) |
| `cad/omafon_gehaeuse.scad` | Handset housing: pruefstueck, deckel (with switch plate), wanne, tastengitter, akkudeckel, notrufklappe, lautstaerke_*, hoererkopf, hoermuschel; STL in print orientation |
| `cad/omafon_ladeschale.scad` | Charging cradle with speaker, spring contacts, coding rib |
| `docs/druckteile.md` | Parts list, print settings, purchased parts, assembly (also shipped in the STL package) |
| `config.festnetz.example.yaml`, `config.hybrid.example.yaml` | Example configurations (placeholders only) |
| `docs/stueckliste.md`, `docs/verkabelung.md` | Bill of materials with prices, wiring/pin assignment of both variants |
| `cad/omafon_tasten.scad` | Key caps and key front, parametric |
| `systemd/omafon.service` | Service with watchdog |

## Commands

```bash
pip install -r requirements-dev.txt                       # PyYAML only
python3 -m unittest discover -s tests -v                  # tests
python3 -m omafon.main --config config.festnetz.example.yaml --sim  # landline simulator (data in ./sim-data)
python3 -m omafon.main --config config.hybrid.example.yaml --sim    # hybrid simulator
python3 -m tools.prerender /etc/omafon/config.yaml        # pre-render announcements (Pi)
openscad -D 'teil="ziffer"' -D 'ziffer="5"' -o taste_5.stl cad/omafon_tasten.scad
openscad -D 'teil="ziffer"' -D 'ziffer="5"' -D 'farbteil="zeichen"' -o taste_5_zeichen.stl cad/omafon_tasten.scad
openscad -D 'variante="hybrid"' -D 'teil="wanne"' -o wanne.stl cad/omafon_gehaeuse.scad
```

In the simulator: keys `0-9 * #`, `a` call, `h` hang up, `m` message, `i` info,
`L<key>` long press, `sos` emergency call; network: `!ring <no>`, `!sms <no> <text>`, `!sag <text>`.

## Rules

1. **Key press → announcement must come immediately.** Digits are announced on the
   `down` event already. Event handlers never block; long sequences run as a
   job (`start_job`), short announcements via `speak()`. No synthesis, no I/O and no
   `await` on slow things on the path between key press and announcement.
2. **The emergency call must never depend on I²C.** SOS button and cover are wired
   directly to Pi GPIOs (`PI_INPUTS`) and are polled even if the MCP23017 fails.
   A failed amplifier (TPA2016) must not prevent the emergency call.
3. **Change announcement texts only in the `P` dict in `omafon/phone.py`** (they stay
   German) and re-run `tools/prerender.py` afterwards, otherwise the WAVs are missing
   from the cache and the announcement is delayed.
4. Tests must run without hardware: import hardware libraries (`serial`, `smbus2`,
   `gpiozero`, `vosk`) only locally inside functions.
5. **Never read messages aloud automatically.** Announce new SMS only by a gong (repeated
   every `news_signal_minutes`) and a blinking LED; they are read only on a key press.
   No gong during a call, in menus or during quiet hours.
6. **Keep keys easy to read:** symbols always in a contrasting colour to the cap
   (`FARBEN` in the SCAD file), cap and symbol as separate bodies (`farbteil`).
   **Change handset and cradle dimensions only in `cad/omafon_masse.scad`**, otherwise
   the phone no longer fits the cradle. CAD parts must render without OpenSCAD warnings
   (CI fails otherwise), STL output always in print orientation without supports.
   Switch plates 1.6 mm (8 layers of 0.2 mm), switch cut-out 14.1 mm, clearance 0.3 mm.
   **Ear before keys:** the handset head + earcup must stand higher than any key cap,
   and during a call the hang-up key only hangs up when held (`hangup_hold_s`) – otherwise
   the cheek hangs up.
7. **Phone talks only through `TelephonyBackend`.** New network functions as a method/
   event in the backend, never backend special cases in `phone.py`. Optional capabilities
   (`supports_sms`, `online`, `status_words`) have safe defaults.
8. **Landline: a lost connection is never silent.** `link_lost` is announced and repeated;
   dialling without a connection says so immediately. The backend reconnects by itself.
9. **Caller names only from contacts and the Fritz!Box phone book**, never from the
   SIP display name (freely chosen by the caller → fraud risk).
10. **Hybrid: the emergency call always has a second path.** If one path fails, try the
    other immediately; 110/112 via cellular even without own network. "No network" only
    when both paths are missing. Reject second calls on the other path, never call waiting.
11. Never commit real phone numbers, locations or credentials.
   `config.yaml` is in `.gitignore`; examples belong in `config.festnetz.example.yaml`
   or `config.hybrid.example.yaml`, passwords there only as `PLATZHALTER_…`.
12. **Change the pin assignment only together:** the GPIO/MCP assignment is in
   `omafon/hardware.py` and `docs/verkabelung.md` (+ `verkabelung.de.md`) – always update all of them.
