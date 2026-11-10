# Omafon – software

*English · [Deutsch](README.de.md)*

[![CI](https://github.com/2eno/omafon/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/2eno/omafon/actions/workflows/ci.yml)
![Python 3.11 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A talking phone for people with severe visual impairment. The phone speaks German.
Raspberry Pi Zero 2 W, Python 3 (asyncio), two variants:

| Variant | `backend:` | Network | Hardware |
|---|---|---|---|
| Landline | `sip` | Fritz!Box via Wi-Fi (IP phone), answering machine, phone book | handset 30 mm, cradle with speaker |
| Hybrid | `hybrid` | Fritz!Box at home, LTE with SMS and GPS on the go – automatically | additional SIM7600E-H HAT, handset 36 mm ([docs/hybrid.md](docs/hybrid.md)) |

- **Bill of materials:** [docs/stueckliste.md](docs/stueckliste.md)
- **Wiring:** [docs/verkabelung.md](docs/verkabelung.md)
- **Printed parts and assembly:** [docs/druckteile.md](docs/druckteile.md)
- Background: [landline research](docs/festnetz-recherche.md),
  [landline hardware and power budget](docs/festnetz-hardware.md)

All documents are also available in German (`*.de.md`).

![Keypad: white digit caps with raised black digits on a dark front, yellow call key, black hang-up key with a white bar, wide info key](cad/tastenfeld_vorschau.png)

*Preview with the fallback font Liberation Sans; Atkinson Hyperlegible is intended.*

| Handset front | Handset back | Cradle |
|---|---|---|
| ![Handset from the front with key caps, earpiece at the top, microphone and charging contacts at the bottom](cad/gehaeuse_vorschau_vorn.png) | ![Back with red emergency cover, battery cover, speaker grille and coding groove](cad/gehaeuse_vorschau_hinten.png) | ![Cradle with the handset inserted (indicated) and the speaker grille behind it](cad/ladeschale_vorschau.png) |

## Status

**Software tested in the simulator, hardware untested.**

- All tests run without hardware (see CI); the PC simulator (`--sim`) covers dialing,
  calls, SMS, voice dialing, dictation and emergency calls.
- Modem, key matrix, amplifier, battery gauge and housing parts have not yet been
  tried on real hardware.
- **Complete print package:** on every push, CI produces all STL files (artifact
  `omafon-stl`). It contains single- and two-color key caps, the housing and the cradle
  per variant, and the print and assembly guide
  ([docs/druckteile.md](docs/druckteile.md)). None of it has been printed yet.

## New messages

SMS are **not read aloud automatically**. A new message is announced with a gong that
repeats every `news_signal_minutes` (default 10) as long as something is unread; in
addition the LED blinks slowly (`news_led`). During a call or in the quiet hours
(`quiet_hours`) there is no gong, at night only the LED. Messages are read aloud only
when the message key is pressed.

## Keys

The caps are designed for two colors: symbols always in a contrasting color to the cap
(black on white, black on yellow, white on black/red). The colors are in `FARBEN` in
`cad/omafon_tasten.scad`; export them separately with `-D 'farbteil="kappe"'` and
`-D 'farbteil="zeichen"'`.

```
omafon/
  main.py       start, watchdog, PC simulator (--sim)
  phone.py      state machine: dialing, calls, SMS, dictation, emergency call
  telephony.py  TelephonyBackend interface + selection via config.yaml
  modem.py      mobile part of the hybrid: AT driver SIM7600 (+ SimModem)
  sip.py        backend sip: baresip via ctrl_tcp, Fritz!Box, connection monitoring
  sipsim.py     rebuilt baresip + Fritz!Box for tests and --sim
  hybrid.py     backend hybrid: Fritz!Box + mobile, routing, power saving
  fritz.py      TR-064: phone book, answering machine
  notify.py     Telegram/e-mail instead of SMS (landline, optional)
  pdu.py        SMS in PDU mode: umlauts, emojis, long SMS
  audio.py      Piper speech output with cache, tones, TPA2016 amplifier
  stt.py        Vosk speech recognition (names + dictation), optional Whisper server
  hardware.py   keys (MCP23017 + GPIO), debouncing, battery, vibration
  numbers.py    "zwo" instead of "zwei", numbers in groups, time
tools/prerender.py   pre-render the fixed announcements
cad/omafon_masse.scad      shared dimensions handset/cradle, variant
cad/omafon_gehaeuse.scad   handset: test piece, top with switch plate, bottom shell, head part, battery cover, emergency cover …
cad/omafon_tasten.scad     key caps and key front (OpenSCAD)
cad/omafon_ladeschale.scad cradle with speaker
systemd/omafon.service
tests/test_omafon.py       26 tests (core, keys, SMS, emergency, pin assignment), without hardware
tests/test_festnetz.py     30 tests (SIP backend, Fritz!Box, cradle), without hardware
tests/test_hybrid.py       15 tests (routing, emergency, second call, power saving), without hardware
docs/                      bill of materials, wiring, landline research and hardware
```

## Trying it on a PC (without hardware)

```bash
pip install -r requirements-dev.txt     # only PyYAML
python3 -m unittest discover -s tests -v
python3 -m omafon.main --config config.festnetz.example.yaml --sim
```

In the simulator you type keys (`0171`, `a` = call, `h` = hang up, `Lh` = hang up
long/held, `Lm` = message long) and network events (`!ring +491711234567`,
`!sag maria`). The landline backend runs for real against a rebuilt baresip:
`!sms <nr>` puts a message on the answering machine, `!wlan aus` / `!wlan an`
disconnects the Fritz!Box (after 10 s you hear „Keine Verbindung zur Fritzbox“),
`lade` / `ab` puts the phone into the cradle or lifts it.

Hybrid device in the simulator: `--config config.hybrid.example.yaml --sim`, plus
`!mring <nr>` (call to the mobile number), `!ab <nr>` (answering machine),
`!netz aus` / `!netz an` (dead zone). Usage and rules: [docs/hybrid.md](docs/hybrid.md).

## Landline on the Pi (in addition to the installation below)

```bash
sudo apt install baresip ffmpeg python3-fritzconnection
```

Set up the Fritz!Box as described in
[docs/festnetz-recherche.md](docs/festnetz-recherche.md#7-what-to-set-up-in-the-fritzbox),
then copy `config.festnetz.example.yaml` to `/etc/omafon/config.yaml` and replace the
placeholders. Omafon starts baresip itself.

## Hybrid: first test on the modem – BEFORE building the housing

```bash
sudo apt install minicom
minicom -D /dev/ttyAMA0 -b 115200
AT+CPIN?            # SIM ready?
AT+CSQ              # reception (10–31 good)
AT+CNMP=38          # force LTE only
ATD<own mobile number>;   # does it ring and can you hear yourself? -> VoLTE works
AT+CHUP
AT+CNMP=2           # back to automatic
```

If the call doesn’t work in LTE-only mode, the phone will only work until 2G is switched
off (mid/late 2028). Then: test another provider, update the module firmware, or ask
SIMCom support for the right VoLTE profile.

## Installation on the Pi

1. Flash **Raspberry Pi OS Lite 64-bit**. `raspi-config`: I²C on, serial port on, login
   console on it off.
2. Add to `/boot/firmware/config.txt`:
   ```
   enable_uart=1
   dtoverlay=disable-bt
   dtparam=watchdog=on
   ```
   In `/etc/systemd/system.conf`: `RuntimeWatchdogSec=15` (hardware watchdog).
3. Packages:
   ```bash
   sudo apt install python3-serial python3-smbus2 python3-gpiozero python3-yaml \
                    alsa-utils espeak-ng
   sudo pip install --break-system-packages vosk
   ```
4. **Piper** (speech output): unpack the release `piper_linux_aarch64.tar.gz` from the
   rhasspy/piper project to `/opt/omafon/piper/`. Put the voice `de_DE-thorsten-medium`
   (or `-low`, faster) from `rhasspy/piper-voices` into `/opt/omafon/voices/`. Also try
   the female voices `kerstin` and `ramona` – grandma decides. *Note:* Piper is now
   developed further as `piper1-gpl`; its command line has different options – then
   adjust `Audio.synth()`.
5. Unpack the **Vosk model** `vosk-model-small-de-0.15` to `/opt/omafon/`.
6. Code to `/opt/omafon`, configuration to `/etc/omafon/config.yaml`, create the user
   `omafon` (groups audio, dialout, gpio, i2c), data partition `/data`.
7. `sudo python3 -m tools.prerender /etc/omafon/config.yaml` – generates all fixed
   announcements.
8. `sudo cp systemd/omafon.service /etc/systemd/system/ && sudo systemctl enable --now omafon`
9. Finally `raspi-config` → Performance → **Overlay File System** on. The system is then
   read-only and survives power cuts. Only `/data` stays writable.

## Names for voice dialing

Vosk only recognizes words from its vocabulary. Unusual names (“Zeno”) are often
missing. That’s why every contact has `spoken:` – enter words there that grandma says
anyway: `sohn`, `tochter`, `enkel`, `doktor` (son, daughter, grandchild, doctor). Test
with `!sag` in the simulator, on the Pi with a short Python call of
`Recognizer.listen_name()`.

## What’s still missing / deliberately open

- Confirmation “press key 1” for the recipient of an emergency call (check DTMF
  detection).
- A real load measurement for the battery life.
- Check the TPA2016 register values on the real chip (comment in `audio.py`).

## License

MIT – see [LICENSE](LICENSE).
