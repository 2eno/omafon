"""Startpunkt.  python -m omafon.main --config /etc/omafon/config.yaml
             python -m omafon.main --config config.example.yaml --sim   (am PC testen)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import sys
import threading

from . import config as config_mod
from .phone import Phone

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
Sprache: !sag <text>  (nächstes Ergebnis der Spracherkennung)
"""

KEYMAP = {"a": "CALL", "h": "HANGUP", "m": "MSG", "i": "INFO", "+": "VOL_UP", "-": "VOL_DOWN"}


def sim_console(loop, events, hw, modem, stt) -> None:
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


async def amain(args) -> None:
    cfg = config_mod.load(args.config)
    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()
    if args.sim:
        from .audio import SimAudio
        from .hardware import SimHardware
        from .modem import SimModem
        from .stt import SimRecognizer
        cfg.data_dir = args.data or "./sim-data"
        audio, hw = SimAudio(cfg), SimHardware(cfg, events)
        modem, stt = SimModem(events), SimRecognizer()
        await modem.start()
        threading.Thread(target=sim_console, args=(loop, events, hw, modem, stt), daemon=True).start()
    else:
        from .audio import TPA2016, Audio
        from .hardware import Hardware
        from .modem import Modem
        from .stt import Recognizer
        try:
            amp = TPA2016()
        except OSError as e:
            log.error("TPA2016 fehlt: %s", e)
            amp = None
        audio = Audio(cfg, amp)
        hw = Hardware(cfg, events, loop)
        modem = Modem(cfg.serial_port, cfg.serial_baud, events, loop)
        await modem.start()
        stt = Recognizer(cfg)
    phone = Phone(cfg, audio, modem, stt, hw, events)
    await asyncio.gather(phone.run(), ticker(events), watchdog(phone))


def main() -> None:
    ap = argparse.ArgumentParser(description="Omafon – sprechendes Telefon")
    ap.add_argument("--config", default="/etc/omafon/config.yaml")
    ap.add_argument("--sim", action="store_true", help="ohne Hardware am PC testen")
    ap.add_argument("--data", help="Datenordner (Simulation)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
