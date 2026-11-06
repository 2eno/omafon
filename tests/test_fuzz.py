"""Zufallsfolgen von Tasten, Netz-Ereignissen und Zeit gegen den Zustandsautomaten.

Prüft nach jedem Schritt Invarianten, die ein Mensch am Telefon sofort merken
würde: Telefon "in Ruhe", obwohl ein Gespräch läuft; Klingeln ohne Anruf; ein
liegen gebliebenes Gespräch, das alle weiteren Anrufe verschluckt …

Fest eingestellte Startwerte, damit Fehler reproduzierbar sind. Gründlicher:
    OMAFON_FUZZ_SEEDS=200 python3 -m unittest tests.test_fuzz
"""
import asyncio
import datetime as dt
import logging
import os
import random
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omafon import config
from omafon.audio import SimAudio
from omafon.hardware import KeyEvent, SimHardware
from omafon.modem import SimModem
from omafon.phone import S, Phone
from omafon.stt import SimRecognizer

CFG = Path(__file__).resolve().parents[1] / "config.hybrid.example.yaml"
KEYS = list("0123456789*#") + ["CALL", "HANGUP", "MSG", "INFO", "VOL_UP", "VOL_DOWN"]
NUMBERS = ["+491711234567", "+491609876543", "+491525550000", "030111222", "", "+4930999"]
SEEDS = int(os.environ.get("OMAFON_FUZZ_SEEDS", "6"))
STEPS = 200


class _Errors(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.items: list[str] = []

    def emit(self, record):
        if record.exc_info:
            self.items.append("".join(traceback.format_exception(*record.exc_info)))


class FuzzTests(unittest.IsolatedAsyncioTestCase):
    async def run_seed(self, seed: int) -> list[str]:
        rnd = random.Random(seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = config.load(CFG)
        cfg.data_dir = tmp.name
        cfg.sos_cancel_window_s = 0.01
        cfg.emergency_ring_seconds = 0.02
        cfg.emergency_rounds = 1
        clock = [dt.datetime(2026, 11, 5, 12, 0)]
        q = asyncio.Queue()
        audio = SimAudio(cfg, echo=False)
        modem = SimModem(q, echo=False)
        hw = SimHardware(cfg, q, echo=False)
        stt = SimRecognizer()
        phone = Phone(cfg, audio, modem, stt, hw, q, clock=lambda: clock[0])
        phone.pause_s = 0.001
        await phone.startup()
        trace: list[str] = []
        found: list[str] = []

        def flag(what):
            found.append(f"Startwert {seed}: {what}\n  zuletzt: " + " | ".join(trace[-10:]))

        async def drain():
            for _ in range(3):
                while not q.empty():
                    try:
                        await phone.handle(q.get_nowait())
                    except Exception:
                        flag(traceback.format_exc())
                await asyncio.sleep(0)

        def put_key(k, kinds, held=0.1):
            for kd in kinds:
                q.put_nowait(KeyEvent(k, kd, held))

        for _ in range(STEPS):
            r = rnd.random()
            if r < 0.45:
                k, kind, held = rnd.choice(KEYS), rnd.choice(["short"] * 3 + ["long"]), rnd.choice([0.1, 0.6, 1.3])
                trace.append(f"{k} {kind}")
                put_key(k, ["down", kind, "up"], held)
            elif r < 0.50:
                seq = rnd.choice([["down", "long", "up"], ["down", "short", "up"], ["down"]])
                trace.append(f"SOS {'/'.join(seq)}")
                put_key("SOS", seq)
            elif r < 0.54:
                kd = rnd.choice(["down", "up"])
                trace.append(f"Ladeschale {kd}")
                hw.charging = kd == "down"
                put_key("CHARGER", [kd])
            elif r < 0.64:
                n = rnd.choice(NUMBERS)
                trace.append(f"Anruf {n or 'unterdrückt'}")
                modem.inject_call(n)
            elif r < 0.76:
                k = rnd.choice(["call_begin", "call_end", "no_carrier", "busy", "no_answer", "missed", "ring"])
                trace.append(k)
                modem.inject(k)
            elif r < 0.82:
                n = rnd.choice(NUMBERS[:4])
                trace.append(f"SMS {n}")
                modem.inject_sms(n, rnd.choice(["Hallo", "status", "x" * 300, "Grüße 😀" * 20]))
            elif r < 0.85:
                k = rnd.choice(["link_lost", "link_ok"])
                trace.append(k)
                modem.inject(k, rnd.choice(["", "no_network", "network_ok", "unbekannt"]))
            elif r < 0.88:
                trace.append("Spracherkennung")
                stt.answers.put_nowait(rnd.choice(["peter", "maria", "quatsch", "", "Ich komme morgen"]))
            elif r < 0.90:
                trace.append("Neustart angefordert")
                phone.request_restart("settings_restart")
                phone.restart_event.clear()
            elif r < 0.93:
                modem.fail_alive = rnd.random() < 0.5
                modem.csq = rnd.choice([0, 99, 15, 25])
                trace.append(f"Modem csq={modem.csq}")
            else:
                secs = rnd.choice([1, 5, 30, 61, 200, 3600])
                trace.append(f"+{secs}s")
                clock[0] += dt.timedelta(seconds=secs)
                for _ in range(min(secs, 65)):
                    q.put_nowait("tick")
            await drain()
            await asyncio.sleep(rnd.choice([0, 0.001, 0.005]))
            await drain()

            busy = phone.job is not None and not phone.job.done()
            st = phone.state
            if st != S.RINGING and phone.ring_task and not phone.ring_task.done():
                flag(f"klingelt im Zustand {st.name}")
            if st == S.RINGING and not (phone.ring_task and not phone.ring_task.done()):
                flag("Zustand RINGING ohne Klingeln")
            if st == S.IDLE and phone.call is not None and not busy:
                if phone.call.ended.is_set():
                    flag("beendetes Gespräch liegt herum (verschluckt neue Anrufe)")
                elif phone.call.answered.is_set():
                    flag("in Ruhe, obwohl ein Gespräch läuft (Auflegen geht nicht)")
            if st == S.IN_CALL and phone.call is None and not busy:
                flag("IN_CALL ohne Gespräch")
            if st == S.SOS and not busy:
                flag("SOS ohne laufenden Notruf")
            if st == S.READING and not phone.playlist:
                flag("READING ohne Nachrichten")
            if not 1 <= audio.volume <= 5:
                flag(f"Lautstärke {audio.volume}")
            if found:
                break
        phone.cancel_job()
        phone.stop_ringing()
        for t in list(phone._bg):
            t.cancel()
        await asyncio.sleep(0)
        return found

    async def test_random_sequences_keep_invariants(self):
        errors = _Errors()
        logging.getLogger().addHandler(errors)
        self.addCleanup(logging.getLogger().removeHandler, errors)
        found = []
        for seed in range(SEEDS):
            found += await self.run_seed(seed)
        self.assertEqual(found, [], "\n\n".join(found))
        self.assertEqual(errors.items, [], "\n".join(errors.items[:3]))


if __name__ == "__main__":
    unittest.main()
