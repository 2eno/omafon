"""Startpunkt.  python -m omafon.main --config /etc/omafon/config.yaml
             python -m omafon.main --config config.festnetz.example.yaml --sim   (am PC testen)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import sys
import threading

from . import __version__
from . import config as config_mod
from .phone import Phone
from .telephony import create_backend

log = logging.getLogger("omafon")


def sd_notify(msg: str) -> None:
    """systemd-Watchdog ohne Zusatzpaket. Stirbt die Hauptschleife, startet systemd neu."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
        s.sendto(msg.encode(), addr)


async def ticker(events: asyncio.Queue) -> None:
    while True:
        await asyncio.sleep(1)
        events.put_nowait("tick")


async def network_time(clock, backend) -> None:
    """Solange die Systemuhr nicht synchron ist (kein WLAN/NTP), Netzzeit vom
    Mobilfunk übernehmen – sonst sagte die Info-Taste eine falsche Uhrzeit an."""
    while True:
        if not clock.synchronized():
            try:
                t = await backend.network_time()
            except Exception as e:                      # nie den Start gefährden
                log.warning("Netzzeit: %r", e)
                t = None
            if t is not None:
                clock.set_network_time(t)
        await asyncio.sleep(600 if clock.known() else 30)


async def watchdog(phone: Phone) -> None:
    sd_notify("READY=1")
    last = -1
    while True:
        await asyncio.sleep(10)
        if phone.ticks != last:          # Hauptschleife verarbeitet noch Ereignisse
            sd_notify("WATCHDOG=1")
            last = phone.ticks


SIM_HELP = """
Tasten:  0-9 * #   a=Anrufen  h=Auflegen  m=Nachricht  i=Info  + - =Lautstärke
         L<taste> = lang drücken (L1 Kurzwahl, Lm Diktat, Lh alles löschen)
         auf / zu = Notruf-Klappe   sos = Notrufknopf 3 s halten   sos- = zu früh los
         lade / ab = Ladeschale
Netz:    !ring <nr>   !sms <nr> <text>   !annahme   !ende   !besetzt
         Festnetz (backend: sip): !sms legt eine Anrufbeantworter-Nachricht ab,
         !wlan aus / !wlan an trennt bzw. verbindet die Fritz!Box
         Hybrid: !ring = Festnetz wenn zu Hause, !mring = Handynummer, !sms = SMS,
         !ab <nr> = Anrufbeantworter, !wlan aus/an, !netz aus/an (Funkloch)
Sprache: !sag <text>  (nächstes Ergebnis der Spracherkennung)
"""

KEYMAP = {"a": "CALL", "h": "HANGUP", "m": "MSG", "i": "INFO", "+": "VOL_UP", "-": "VOL_DOWN"}


def sim_console(loop, events, hw, modem, stt) -> None:
    """modem = Simulator-Steuerung mit inject_call, inject_sms, inject (und ggf. link)."""
    from .hardware import KeyEvent
    print(SIM_HELP, flush=True)

    def put(ev):
        loop.call_soon_threadsafe(events.put_nowait, ev)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line.startswith("!"):
            cmd, _, rest = line[1:].partition(" ")
            if cmd == "ring":
                loop.call_soon_threadsafe(modem.inject_call, rest or "+491711234567")
            elif cmd == "sms":
                nr, _, text = rest.partition(" ")
                loop.call_soon_threadsafe(modem.inject_sms, nr, text)
            elif cmd == "annahme":
                loop.call_soon_threadsafe(modem.inject, "call_begin")
            elif cmd == "ende":
                loop.call_soon_threadsafe(modem.inject, "call_end")
            elif cmd == "besetzt":
                loop.call_soon_threadsafe(modem.inject, "busy")
            elif cmd == "sag":
                loop.call_soon_threadsafe(stt.answers.put_nowait, rest)
            elif cmd == "wlan" and hasattr(modem, "link"):
                loop.call_soon_threadsafe(modem.link, rest.strip() != "aus")
            elif cmd == "netz" and hasattr(modem, "netz"):
                loop.call_soon_threadsafe(modem.netz, rest.strip() != "aus")
            elif cmd == "mring" and hasattr(modem, "inject_mobile_call"):
                loop.call_soon_threadsafe(modem.inject_mobile_call, rest or "+491711234567")
            elif cmd == "ab" and hasattr(modem, "inject_voicemail"):
                loop.call_soon_threadsafe(modem.inject_voicemail, rest or "+491609876543")
            continue
        if line in ("auf", "zu"):
            put(KeyEvent("SOS_COVER", "down" if line == "auf" else "up"))
        elif line in ("sos", "sos-"):
            put(KeyEvent("SOS", "down"))
            put(KeyEvent("SOS", "long" if line == "sos" else "short"))
            put(KeyEvent("SOS", "up"))
        elif line in ("lade", "ab"):
            hw.charging = line == "lade"
            put(KeyEvent("CHARGER", "down" if line == "lade" else "up"))
        else:
            long = line.startswith("L") and len(line) == 2
            ch = line[1] if long else line
            for c in ([ch] if long else list(ch)):
                key = KEYMAP.get(c, c)
                put(KeyEvent(key, "down"))
                put(KeyEvent(key, "long" if long else "short"))
                put(KeyEvent(key, "up"))


def use_saved_config(seed_path: str, cfg):
    """Die App speichert Einstellungen in <data_dir>/config.yaml – /etc ist mit dem
    Overlay-Dateisystem schreibgeschützt. Gibt es diese Datei, gilt sie; ist sie
    kaputt, startet das Telefon mit der Vorlage aus /etc (nie ohne Konfiguration).
    Ist die Verwaltung an und die Datei fehlt, wird die Vorlage dorthin kopiert."""
    import shutil
    from pathlib import Path
    saved = Path(cfg.data_dir) / "config.yaml"
    if saved.resolve() == Path(seed_path).resolve():
        return seed_path, cfg
    if saved.exists():
        import yaml
        try:
            return str(saved), config_mod.load(saved)
        except (OSError, ValueError, TypeError, yaml.YAMLError) as e:
            log.error("%s ungültig (%s) – starte mit %s", saved, e, seed_path)
            return seed_path, cfg
    if (getattr(cfg, "admin", None) or {}).get("enabled", True):
        try:
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(seed_path, saved)
            os.chmod(saved, 0o600)
            return str(saved), cfg
        except OSError as e:
            log.error("Kann %s nicht anlegen: %s", saved, e)
    return seed_path, cfg


async def amain(args) -> None:
    config_path = args.config
    if args.sim and args.admin:
        # Die App darf in der Simulation nicht die Vorlage im Repository ändern
        import shutil
        from pathlib import Path
        data = Path(args.data or "./sim-data")
        data.mkdir(parents=True, exist_ok=True)
        copy = data / "config.yaml"
        if not copy.exists():
            shutil.copy(args.config, copy)
        config_path = str(copy)
    cfg = config_mod.load(config_path)
    if not args.sim:
        config_path, cfg = use_saved_config(config_path, cfg)
    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()
    if args.sim:
        from .audio import SimAudio
        from .hardware import SimHardware
        from .stt import SimRecognizer
        cfg.data_dir = args.data or "./sim-data"
        audio, hw = SimAudio(cfg), SimHardware(cfg, events)
        modem, control = create_backend(cfg, events, loop, sim=True)
        stt = SimRecognizer()
        await modem.start()
        threading.Thread(target=sim_console, args=(loop, events, hw, control, stt), daemon=True).start()
    else:
        from .audio import TPA2016, Audio
        from .hardware import Hardware
        from .stt import Recognizer
        try:
            amp = TPA2016()
        except OSError as e:
            log.error("TPA2016 fehlt: %s", e)
            amp = None
        audio = Audio(cfg, amp)
        await audio.check_devices()   # vor baresip: es übernimmt cfg.audio_device
        hw = Hardware(cfg, events, loop)
        modem, _ = create_backend(cfg, events, loop)
        await modem.start()
        stt = Recognizer(cfg)
    if args.sim:
        phone = Phone(cfg, audio, modem, stt, hw, events)
    else:
        import time
        from .clock import Clock
        clock = Clock()
        phone = Phone(cfg, audio, modem, stt, hw, events, clock=clock.now,
                      monotonic=time.monotonic, time_known=clock.known)
    tasks = [phone.run(), ticker(events), watchdog(phone)]
    if not args.sim:
        tasks.append(network_time(clock, modem))

    # Updates (A/B mit Rückfall) und Companion-App
    from .update import CONFIRM_AFTER_S, Updater
    updater = Updater(cfg.data_dir, __version__, cfg.update_url, cfg.update_public_key)
    admin_opts = getattr(cfg, "admin", None) or {}
    if admin_opts.get("enabled", True) and (not args.sim or args.admin):
        from .admin import AdminServer
        if args.sim and args.admin_port:
            cfg.admin = {**admin_opts, "port": args.admin_port}
        admin = AdminServer(cfg, config_path, phone, updater)
        try:
            await admin.start()
            phone.admin = admin
        except Exception as e:        # Port belegt, openssl fehlt …: Telefon läuft trotzdem
            log.error("Verwaltung nicht gestartet: %r", e)

    async def confirm_update():
        start = phone.ticks
        await asyncio.sleep(CONFIRM_AFTER_S)
        if phone.ticks - start >= CONFIRM_AFTER_S // 2:   # Hauptschleife lief wirklich
            updater.confirm()         # neue Version lief stabil -> kein Rückfall mehr
        else:
            log.error("Hauptschleife hängt – Version wird nicht bestätigt")

    tasks.append(confirm_update())
    runner = asyncio.gather(*tasks)
    restart = asyncio.create_task(phone.restart_event.wait())
    await asyncio.wait({runner, restart}, return_when=asyncio.FIRST_COMPLETED)
    if restart.done():
        log.info("Neustart angefordert – systemd startet Omafon neu")
        runner.cancel()
        sys.exit(0)
    await runner


def main() -> None:
    ap = argparse.ArgumentParser(description="Omafon – sprechendes Telefon")
    ap.add_argument("--config", default="/etc/omafon/config.yaml")
    ap.add_argument("--sim", action="store_true", help="ohne Hardware am PC testen")
    ap.add_argument("--data", help="Datenordner (Simulation)")
    ap.add_argument("--admin", action="store_true", help="Simulation: Verwaltung für die App einschalten")
    ap.add_argument("--admin-port", type=int, default=0, help="Simulation: Port der Verwaltung")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
