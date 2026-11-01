# Omafon – Software

[![CI](https://github.com/2eno/omafon/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/2eno/omafon/actions/workflows/ci.yml)
![Python 3.11 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-green)](LICENSE)

Sprechendes Telefon für Menschen mit starker Sehbehinderung.
Raspberry Pi Zero 2 W + Waveshare SIM7600E-H 4G HAT, Python 3 (asyncio).

![Tastenfeld: weiße Ziffernkappen mit erhabenen Ziffern auf dunkler Front, gelbe Anruftaste, schwarze Auflegetaste, breite Info-Taste](cad/tastenfeld_vorschau.png)

## Status

**Software im Simulator getestet, Hardware ungetestet.**

- Alle Tests laufen ohne Hardware (siehe CI); der PC-Simulator (`--sim`) deckt
  Wählen, Anrufe, SMS, Sprachwahl, Diktat und Notruf ab.
- Modem, Tastenmatrix, Verstärker, Akku-Messung und Gehäuseteile sind noch
  nicht an echter Hardware erprobt.
- Die STL-Dateien der Tastenkappen und der Front werden bei jedem Push von der
  CI erzeugt (Artefakt `omafon-stl`).

```
omafon/
  main.py       Start, Watchdog, PC-Simulator (--sim)
  phone.py      Zustandsautomat: Wählen, Anrufe, SMS, Diktat, Notruf
  modem.py      AT-Treiber SIM7600 (+ SimModem)
  pdu.py        SMS im PDU-Modus: Umlaute, Emojis, lange SMS
  audio.py      Piper-Sprachausgabe mit Cache, Töne, TPA2016-Verstärker
  stt.py        Vosk-Spracherkennung (Namen + Diktat), optional Whisper-Server
  hardware.py   Tasten (MCP23017 + GPIO), Entprellung, Akku, Vibration
  numbers.py    "zwo" statt "zwei", Nummern in Gruppen, Uhrzeit
tools/prerender.py   feste Ansagen vorab erzeugen
cad/omafon_tasten.scad  Tastenkappen und Tastenfront (OpenSCAD)
systemd/omafon.service
tests/test_omafon.py    22 Tests, laufen ohne Hardware
docs/                   Stückliste und Verkabelung
```

## Am PC ausprobieren (ohne Hardware)

```bash
pip install -r requirements-dev.txt     # nur PyYAML
python3 -m unittest discover -s tests -v
python3 -m omafon.main --config config.example.yaml --sim
```

Im Simulator tippst du Tasten (`0171`, `a` = Anrufen, `h` = Auflegen, `Lm` = Nachricht lang)
und Netzereignisse (`!ring +491711234567`, `!sms +491609876543 Hallo Mama`, `!sag maria`).

## Erster Test am Modem – VOR dem Gehäusebau

```bash
sudo apt install minicom
minicom -D /dev/ttyAMA0 -b 115200
AT+CPIN?            # SIM bereit?
AT+CSQ              # Empfang (10–31 gut)
AT+CNMP=38          # nur LTE erzwingen
ATD<eigene Handynummer>;   # klingelt es und hört man sich? -> VoLTE läuft
AT+CHUP
AT+CNMP=2           # zurück auf automatisch
```

Klappt der Anruf im LTE-only-Modus nicht, funktioniert das Telefon nur bis zur
2G-Abschaltung (Mitte/Ende 2028). Dann: anderen Anbieter testen, Modul-Firmware
aktualisieren oder beim SIMCom-Support nach dem passenden VoLTE-Profil fragen.

## Installation auf dem Pi

1. **Raspberry Pi OS Lite 64 Bit** flashen. `raspi-config`: I²C an, serielle
   Schnittstelle an, Login-Konsole darauf aus.
2. `/boot/firmware/config.txt` ergänzen:
   ```
   enable_uart=1
   dtoverlay=disable-bt
   dtparam=watchdog=on
   ```
   In `/etc/systemd/system.conf`: `RuntimeWatchdogSec=15` (Hardware-Watchdog).
3. Pakete:
   ```bash
   sudo apt install python3-serial python3-smbus2 python3-gpiozero python3-yaml \
                    alsa-utils espeak-ng
   sudo pip install --break-system-packages vosk
   ```
4. **Piper** (Sprachausgabe): Release `piper_linux_aarch64.tar.gz` aus dem
   Projekt rhasspy/piper nach `/opt/omafon/piper/` entpacken. Stimme
   `de_DE-thorsten-medium` (oder `-low`, schneller) aus `rhasspy/piper-voices` nach
   `/opt/omafon/voices/`. Probiere auch die Frauenstimmen `kerstin` und `ramona` –
   Oma entscheidet. *Hinweis:* Piper wird inzwischen als `piper1-gpl` weiterentwickelt;
   dessen Kommandozeile hat andere Optionen – dann `Audio.synth()` anpassen.
5. **Vosk-Modell** `vosk-model-small-de-0.15` nach `/opt/omafon/` entpacken.
6. Code nach `/opt/omafon`, Konfiguration nach `/etc/omafon/config.yaml`, Benutzer
   `omafon` anlegen (Gruppen audio, dialout, gpio, i2c), Datenpartition `/data`.
7. `sudo python3 -m tools.prerender /etc/omafon/config.yaml` – erzeugt alle festen Ansagen.
8. `sudo cp systemd/omafon.service /etc/systemd/system/ && sudo systemctl enable --now omafon`
9. Zum Schluss `raspi-config` → Performance → **Overlay File System** an. Das System
   ist dann schreibgeschützt und übersteht Stromausfälle. Nur `/data` bleibt beschreibbar.

## Namen für die Sprachwahl

Vosk erkennt nur Wörter aus seinem Wortschatz. Exotische Namen ("Zeno") fehlen
oft. Darum hat jeder Kontakt `spoken:` – dort Wörter eintragen, die Oma ohnehin
sagt: `sohn`, `tochter`, `enkel`, `doktor`. Mit `!sag` im Simulator testen,
auf dem Pi mit einem kurzen Python-Aufruf von `Recognizer.listen_name()`.

## Was noch fehlt / bewusst offen

- Bestätigung "Taste 1 drücken" beim Notruf-Empfänger (DTMF-Erkennung prüfen).
- Echte Lastmessung für die Akkulaufzeit.
- TPA2016-Registerwerte am echten Chip prüfen (Kommentar in `audio.py`).

## Lizenz

MIT – siehe [LICENSE](LICENSE).
