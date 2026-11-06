"""Tests für das Hybrid-Backend (Fritz!Box zu Hause + Mobilfunk unterwegs).

Festnetz: echtes BaresipBackend gegen FakeBaresip. Mobilfunk: SimModem.

    python3 -m unittest discover -s tests -v
"""
import asyncio
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omafon import config
from omafon.audio import SimAudio
from omafon.hardware import KeyEvent, SimHardware
from omafon.hybrid import HybridBackend, HybridSimulator
from omafon.phone import P, S, Phone
from omafon.stt import SimRecognizer
from omafon.telephony import create_backend

CFG = Path(__file__).resolve().parents[1] / "config.hybrid.example.yaml"


class HybridTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = config.load(CFG)
        self.cfg.data_dir = self.tmp.name
        self.cfg.sip.update(ring_repeat_s=0.05, wifi_reset_cmd="")
        self.cfg.sos_cancel_window_s = 0.05
        self.cfg.emergency_ring_seconds = 0.2
        self.cfg.emergency_rounds = 1
        self.t = 1000.0
        self.clock = dt.datetime(2026, 11, 1, 18, 21)
        self.q = asyncio.Queue()
        self.sim = HybridSimulator(self.cfg, echo=False)
        self.hy = self.sim.backend(self.q, clock=lambda: self.t)
        self.audio = SimAudio(self.cfg, echo=False)
        self.hw = SimHardware(self.cfg, self.q, echo=False)
        self.stt = SimRecognizer()
        self.phone = Phone(self.cfg, self.audio, self.hy, self.stt, self.hw, self.q,
                           clock=lambda: self.clock)
        await self.hy.start()
        self.assertTrue(await self.until(lambda: self.hy.home.online and self.hy.mobile_ok))
        await self.phone.startup()
        self.audio.spoken.clear()

    async def asyncTearDown(self):
        self.phone.cancel_job()
        await self.hy.stop()
        await self.sim.sip.server.stop()
        self.tmp.cleanup()

    # ------------------------------------------------------------ Hilfen
    async def until(self, cond, timeout=2.0):
        for _ in range(int(timeout / 0.01)):
            if cond():
                return True
            await asyncio.sleep(0.01)
        return False

    async def pump(self, rounds=30):
        for _ in range(rounds):
            while not self.q.empty():
                await self.phone.handle(self.q.get_nowait())
            await asyncio.sleep(0.005)

    async def pump_until(self, cond, max_rounds=1500):
        for _ in range(max_rounds):
            if cond():
                return True
            await self.pump(1)
        return False

    async def press(self, key, long=False, held=0.1):
        self.hw.press(key, long, held)
        await self.pump()

    async def dial(self, number):
        for d in number:
            await self.press(d)
        await self.press("CALL")

    def said(self):
        return " | ".join(self.audio.spoken)

    def sip_dials(self):
        return [p for c, p in self.sim.sip.server.commands if c == "dial"]

    def modem_dials(self):
        return [m for m in self.sim.modem.log if m.startswith("ATD")]

    async def leave_home(self):
        self.sim.link(False)
        self.assertTrue(await self.until(lambda: not self.hy.home.online))
        await self.hy.tick()

    # ------------------------------------------------------------ Tests
    def test_backend_selection(self):
        loop = asyncio.get_event_loop()
        b, ctl = create_backend(self.cfg, asyncio.Queue(), loop, sim=True)
        self.assertIsInstance(b, HybridBackend)
        self.assertIsInstance(ctl, HybridSimulator)

    async def test_at_home_calls_go_over_fritzbox(self):
        await self.dial("0301234")
        self.assertTrue(await self.pump_until(lambda: self.sip_dials()))
        self.assertEqual(self.sip_dials(), ["sip:0301234@fritz.box"])
        self.assertEqual(self.modem_dials(), [])
        self.assertEqual(self.hy.active, "home")

    async def test_away_calls_go_mobile_without_fritzbox_complaint(self):
        await self.leave_home()
        self.t += 60
        await self.hy.tick()
        await self.pump()
        self.assertNotIn("Fritzbox", self.said())          # unterwegs ist das normal
        self.assertNotIn(P["no_network"], self.said())
        await self.dial("0301234")
        self.assertTrue(await self.pump_until(lambda: self.modem_dials()))
        self.assertEqual(self.modem_dials(), ["ATD0301234;"])
        self.assertEqual(self.sip_dials(), [])

    async def test_fallback_to_mobile_when_fritzbox_refuses(self):
        self.sim.sip.server.fail.add("dial")
        await self.dial("0301234")
        self.assertTrue(await self.pump_until(lambda: self.modem_dials()))
        self.assertEqual(self.hy.active, "mobile")
        self.assertNotIn(P["not_reached"], self.said())

    async def test_weak_wifi_prefers_mobile(self):
        wireless = Path(self.tmp.name) / "wireless"
        head = "Inter-| sta-|   Quality        |   Discarded packets\n face | tstatus | link level noise |\n"
        wireless.write_text(head + "wlan0: 0000   20.  -82.  -256        0      0      0\n")
        self.hy.home.wireless_path = str(wireless)
        self.assertTrue(self.hy.wifi_weak())
        self.assertEqual(self.hy._order("0301234"), ["mobile", "home"])
        self.assertEqual(self.hy._order("112"), ["mobile", "home"])
        wireless.write_text(head + "wlan0: 0000   60.  -55.  -256        0      0      0\n")
        self.assertEqual(self.hy._order("0301234"), ["home", "mobile"])

    async def test_emergency_routing(self):
        self.assertEqual(self.hy._order("112"), ["home", "mobile"])
        await self.hy.dial("112")                            # zu Hause: Festnetz
        self.assertEqual(self.sip_dials(), ["sip:112@fritz.box"])
        await self.hy.hangup()
        self.sim.sip.server.fail.add("dial")                 # Festnetz streikt
        await self.hy.dial("112")
        self.assertEqual(self.modem_dials(), ["ATD112;"])
        await self.hy.hangup()
        await self.leave_home()                              # unterwegs im Funkloch
        self.sim.netz(False)
        self.t += 60
        await self.hy.tick()
        self.assertFalse(self.hy.mobile_ok)
        await self.hy.dial("112")                            # Notruf geht trotzdem
        self.assertEqual(self.modem_dials()[-1], "ATD112;")

    async def test_no_network_only_when_both_are_gone(self):
        await self.leave_home()
        self.sim.netz(False)
        self.t += 31
        await self.hy.tick()                                 # Empfang neu abgefragt
        self.t += 20                                         # Schonfrist + Aufwachzeit vorbei
        await self.hy.tick()
        await self.pump()
        self.assertIn(P["no_network"], self.said())
        self.assertNotIn("Fritzbox", self.said())
        self.audio.spoken.clear()
        await self.dial("0301234")
        await self.pump()
        self.assertIn(P["no_network"], self.said())          # Wählen: sofort Rückmeldung
        self.assertEqual(self.modem_dials(), [])
        self.sim.netz(True)
        self.t += 31
        await self.hy.tick()
        self.assertTrue(await self.pump_until(lambda: P["network_ok"] in self.said()))

    async def test_second_line_is_rejected_during_call(self):
        self.sim.sip.inject_call("+491609876543")            # Festnetz klingelt
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.RINGING))
        await self.press("CALL")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.IN_CALL))
        self.sim.inject_mobile_call("+491711234567")         # Handy klingelt dazwischen
        self.assertTrue(await self.pump_until(lambda: "AT+CHUP" in self.sim.modem.log))
        await self.pump()
        self.assertEqual(self.phone.state, S.IN_CALL)        # Gespräch läuft weiter
        self.assertNotIn("Anruf von Peter", self.said())
        self.sim.inject("call_end")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.IDLE))
        self.assertIsNone(self.hy.active)

    async def test_mobile_call_while_at_home(self):
        self.sim.inject_mobile_call("+491711234567")
        self.assertTrue(await self.pump_until(lambda: "Anruf von Peter." in self.said()))
        await self.press("CALL")
        self.assertIn("ATA", self.sim.modem.log)
        self.assertEqual(self.hy.active, "mobile")

    async def test_sms_and_voicemail_share_the_inbox(self):
        self.sim.inject_sms("+491711234567", "Ich bin gleich da")
        self.sim.inject_voicemail("01609876543")
        self.assertTrue(await self.pump_until(lambda: len(self.phone.inbox) == 2))
        await self.press("MSG")
        self.assertTrue(await self.pump_until(lambda: P["read_hint"] in self.said()))
        self.assertIn("Ich bin gleich da", self.said())
        await self.press("MSG")
        self.assertTrue(await self.pump_until(lambda: any(s.startswith("<abspielen") for s in self.audio.spoken)))
        self.assertIn(P["voicemail"], self.said())

    async def test_sos_away_uses_sms_and_gps(self):
        await self.leave_home()
        self.q.put_nowait(KeyEvent("SOS", "down"))
        self.q.put_nowait(KeyEvent("SOS", "long"))
        self.assertTrue(await self.pump_until(lambda: "ATD+491711234567;" in self.sim.modem.log, 3000))
        self.sim.inject("call_begin")
        self.assertTrue(await self.pump_until(lambda: self.phone.call and self.phone.call.answered.is_set()))
        self.sim.inject("call_end")
        self.assertTrue(await self.pump_until(lambda: P["sos_done"] in self.said()))
        self.assertTrue(await self.pump_until(lambda: any("openstreetmap" in t for _, t in self.sim.modem.sent)))
        self.assertEqual({n for n, _ in self.sim.modem.sent},
                         {"+491711234567", "+491609876543", "+491525550000"})
        self.assertEqual(self.sim.sip.notifier.sent, [])     # echte SMS, kein Push

    async def test_sos_at_home_calls_over_fritzbox_and_uses_home_position(self):
        self.cfg.home_position = [51.0, 10.0]          # Platzhalter, kein echter Ort
        self.q.put_nowait(KeyEvent("SOS", "down"))
        self.q.put_nowait(KeyEvent("SOS", "long"))
        self.assertTrue(await self.pump_until(lambda: "sip:+491711234567@fritz.box" in self.sip_dials(), 3000))
        self.sim.inject("call_begin")
        self.assertTrue(await self.pump_until(lambda: self.phone.call and self.phone.call.answered.is_set()))
        self.sim.inject("call_end")
        self.assertTrue(await self.pump_until(lambda: any("mlat=51.00000" in t for _, t in self.sim.modem.sent)))

    async def test_sos_falls_back_when_fritzbox_drops_call_at_once(self):
        """Regel 10: Festnetz nimmt den Ruf an, bricht ihn aber sofort ab (z. B. 503) –
        der nächste Versuch muss über Mobilfunk gehen, nicht wieder ins Leere."""
        self.cfg.emergency_rounds = 2
        self.q.put_nowait(KeyEvent("SOS", "down"))
        self.q.put_nowait(KeyEvent("SOS", "long"))
        self.assertTrue(await self.pump_until(lambda: "sip:+491711234567@fritz.box" in self.sip_dials(), 3000))
        self.sim.sip.inject("call_end")                     # sofort abgebrochen, nie angenommen
        self.assertTrue(await self.pump_until(lambda: self.modem_dials(), 3000))
        self.assertEqual(self.hy.active, "mobile")
        self.assertEqual(self.hy._order("0301234"), ["mobile", "home"])
        self.t += 601                                        # nach 10 Minuten wieder normal
        self.assertEqual(self.hy._order("0301234"), ["home", "mobile"])
        await self.press("HANGUP")

    async def test_power_saving_mode(self):
        self.hy.opt["home_modem"] = "off"
        await self.hy.tick()
        self.assertTrue(self.hy.radio_on)                    # noch nicht stabil genug
        self.t += 301
        await self.hy.tick()
        self.assertFalse(self.hy.radio_on)
        self.assertIn("AT+CFUN=4", self.sim.modem.log)
        self.assertIn("Mobilfunk ruht", self.hy.status_words())
        await self.hy.send_sms("+491711234567", "Test")      # Notruf-SMS weckt den Funk
        self.assertTrue(self.hy.radio_on)
        self.assertEqual(self.sim.modem.sent[-1], ("+491711234567", "Test"))
        self.t += 301
        await self.hy.tick()
        self.assertFalse(self.hy.radio_on)
        await self.leave_home()                              # Wohnung verlassen
        self.assertTrue(self.hy.radio_on)
        self.assertEqual(self.sim.modem.log.count("AT+CFUN=1"), 2)
        self.t += 5                                          # Aufwachzeit: keine Fehlalarme
        await self.hy.tick()
        await self.pump()
        self.assertNotIn(P["no_network"], self.said())

    async def test_mode_announcements_are_optional(self):
        self.hy.opt["announce_mode"] = True
        await self.hy.tick()
        await self.leave_home()
        self.assertTrue(await self.pump_until(lambda: P["mode_mobile"] in self.said()))
        self.sim.link(True)
        self.assertTrue(await self.until(lambda: self.hy.home.online))
        await self.hy.tick()
        self.assertTrue(await self.pump_until(lambda: P["mode_home"] in self.said()))

    async def test_info_names_both_paths(self):
        await self.press("INFO")
        self.assertTrue(await self.pump_until(lambda: "Mobilfunk" in self.said()))
        self.assertIn("Zu Hause. Verbindung zur Fritzbox gut.", self.said())
        self.assertIn("Mobilfunk: Empfang gut.", self.said())


if __name__ == "__main__":
    unittest.main()
