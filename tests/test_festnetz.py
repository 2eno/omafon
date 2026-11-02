"""Tests für das Festnetz-Backend (SIP über die Fritz!Box) – ohne Hardware und Netz.

Das echte BaresipBackend spricht über TCP mit FakeBaresip (nachgebautes
ctrl_tcp von baresip); die Fritz!Box ist SimFritzBox.

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
from omafon.fritz import download_url, parse_phonebook, parse_tam_list
from omafon.hardware import KeyEvent, SimHardware
from omafon.notify import Notifier
from omafon.phone import P, S, Phone
from omafon.sip import baresip_files, close_kind, dbm_to_csq, ns_encode, ns_read, peer_number
from omafon.sipsim import SipSimulator
from omafon.stt import SimRecognizer
from omafon.telephony import ModemError, ModemEvent, TelephonyBackend, create_backend

CFG = Path(__file__).resolve().parents[1] / "config.festnetz.example.yaml"

PHONEBOOK_XML = """<?xml version="1.0" encoding="utf-8"?>
<phonebooks><phonebook name="Telefonbuch">
 <contact><category>0</category><person><realName>Frau Schmidt</realName></person>
  <telephony nid="2"><number type="home" prio="1" id="0">069 90009100</number>
  <number type="mobile" prio="0" id="1">+49 171 3920001</number></telephony></contact>
 <contact><person><realName></realName></person>
  <telephony><number type="home">0301111</number></telephony></contact>
</phonebook></phonebooks>"""

TAM_XML = """<?xml version="1.0" encoding="utf-8"?>
<Root>
 <Message><Index>1</Index><Tam>0</Tam><Called>069123</Called><Date>01.11.26 18:21</Date>
  <Duration>0:01</Duration><Inbook>1</Inbook><Name>Maria</Name><New>1</New>
  <Number>01609876543</Number><Path>/download.lua?path=/data/tam/rec/rec.0.001</Path></Message>
 <Message><Index>0</Index><Tam>0</Tam><Date>31.10.26 09:05</Date><New>0</New>
  <Number></Number><Path>/download.lua?path=/data/tam/rec/rec.0.000</Path></Message>
</Root>"""


class HelperTests(unittest.TestCase):
    def test_peer_number(self):
        self.assertEqual(peer_number("sip:+491711234567@fritz.box"), "+491711234567")
        self.assertEqual(peer_number("<sip:0301234;user=phone@fritz.box>"), "0301234")
        self.assertEqual(peer_number("sip:**610@fritz.box"), "**610")
        self.assertEqual(peer_number("sip:anonymous@anonymous.invalid"), "")
        self.assertEqual(peer_number(""), "")

    def test_close_kind_and_signal(self):
        self.assertEqual(close_kind("486 Busy Here"), "busy")
        self.assertEqual(close_kind("408 Request Timeout"), "no_answer")
        self.assertEqual(close_kind("Connection reset by peer"), "call_end")
        self.assertEqual(dbm_to_csq(-50), 31)
        self.assertEqual(dbm_to_csq(-95), 0)

    def test_phonebook_xml(self):
        book = parse_phonebook(PHONEBOOK_XML)
        self.assertEqual(book, {"06990009100": "Frau Schmidt", "01713920001": "Frau Schmidt"})

    def test_tam_xml_and_download_url(self):
        msgs = parse_tam_list(TAM_XML)
        self.assertEqual([m.index for m in msgs], [1, 0])
        self.assertTrue(msgs[0].new)
        self.assertEqual(msgs[0].time, dt.datetime(2026, 11, 1, 18, 21))
        self.assertEqual(msgs[1].number, "")
        url = download_url("http://fritz.box:49000/tamcalllist.lua?sid=abc123&tamindex=0", msgs[0].path)
        self.assertEqual(url, "http://fritz.box:49000/download.lua?path=/data/tam/rec/rec.0.001&sid=abc123")
        url = download_url("http://fritz.box:49000/x.lua?sid=s1", "/data/tam/rec/rec.0.000")
        self.assertEqual(url, "http://fritz.box:49000/download.lua?path=/data/tam/rec/rec.0.000&sid=s1")

    def test_baresip_files_keep_password_out_of_config(self):
        cfg = config.load(CFG)
        files = baresip_files(cfg, {**cfg.sip, "ctrl_port": 4444})
        self.assertNotIn("PLATZHALTER_SIP_KENNWORT", files["config"])
        self.assertIn("auth_pass=PLATZHALTER_SIP_KENNWORT", files["accounts"])
        self.assertIn("ctrl_tcp_listen\t\t127.0.0.1:4444", files["config"])
        self.assertIn("<sip:omafon-ip@fritz.box>", files["accounts"])

    def test_example_configs_have_no_real_secrets(self):
        for name in ("config.example.yaml", "config.festnetz.example.yaml", "config.hybrid.example.yaml"):
            text = (CFG.parent / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\d{6,}:[A-Za-z0-9_-]{30,}")      # Telegram-Token
            for line in text.splitlines():
                if "password:" in line:
                    self.assertRegex(line, r"PLATZHALTER|null")

    def test_backend_selection(self):
        cfg = config.load(CFG)
        loop = asyncio.new_event_loop()
        try:
            q = asyncio.Queue()
            b, ctl = create_backend(cfg, q, loop, sim=True)
            self.assertEqual(b.name, "sip")
            self.assertIsInstance(b, TelephonyBackend)
            self.assertIsInstance(ctl, SipSimulator)
            cfg.backend = "sim7600"
            b, ctl = create_backend(cfg, q, loop, sim=True)
            self.assertEqual(b.name, "sim7600")
            cfg.backend = "isdn"
            with self.assertRaises(ValueError):
                create_backend(cfg, q, loop)
        finally:
            loop.close()


class NetstringTests(unittest.IsolatedAsyncioTestCase):
    async def test_roundtrip(self):
        r = asyncio.StreamReader()
        r.feed_data(ns_encode({"command": "dial", "params": "sip:ä@x"}) + ns_encode({"a": 1}))
        self.assertEqual((await ns_read(r))["params"], "sip:ä@x")
        self.assertEqual(await ns_read(r), {"a": 1})


class NotifierTests(unittest.IsolatedAsyncioTestCase):
    async def test_telegram_request(self):
        cfg = config.load(CFG)
        cfg.notify = {"enabled": True, "telegram_token": "TESTTOKEN"}
        cfg.contacts[0].telegram_chat_id = 4711
        seen = []

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"ok": true}'

        def opener(req, timeout):
            seen.append((req.full_url, req.data.decode()))
            return Resp()

        n = Notifier(cfg, opener=opener)
        self.assertTrue(n.can_reach("+491711234567"))
        self.assertFalse(n.can_reach("+491525550000"))     # Enkel: kein Weg eingerichtet
        await n.send_to_number("+491711234567", "NOTRUF von Oma Erika!")
        self.assertEqual(seen[0][0], "https://api.telegram.org/botTESTTOKEN/sendMessage")
        self.assertIn("chat_id=4711", seen[0][1])
        with self.assertRaises(ModemError):
            await n.send_to_number("+491525550000", "x")

    async def test_disabled_by_default(self):
        n = Notifier(config.load(CFG))
        self.assertFalse(n.enabled)
        with self.assertRaises(ModemError):
            await n.send_to_number("+491711234567", "x")


class Base(unittest.IsolatedAsyncioTestCase):
    """Gemeinsamer Aufbau: echtes BaresipBackend gegen FakeBaresip."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = config.load(CFG)
        self.cfg.data_dir = self.tmp.name
        self.cfg.sip.update(ring_repeat_s=0.05, link_grace_s=10, reregister_s=60,
                            restart_s=120, wifi_reset_s=180, wifi_reset_cmd="")
        self.t = 1000.0
        self.q = asyncio.Queue()
        self.sim = SipSimulator(self.cfg, echo=False)
        self.backend = self.sim.backend(self.q, clock=lambda: self.t)
        await self.backend.start()
        self.assertTrue(await self.until(lambda: self.backend.online))

    async def asyncTearDown(self):
        await self.backend.stop()
        await self.sim.server.stop()
        self.tmp.cleanup()

    async def until(self, cond, timeout=2.0):
        for _ in range(int(timeout / 0.01)):
            if cond():
                return True
            await asyncio.sleep(0.01)
        return False

    def drain(self):
        out = []
        while not self.q.empty():
            ev = self.q.get_nowait()
            if isinstance(ev, ModemEvent):
                out.append((ev.kind, ev.data))
        return out

    def commands(self):
        return [c for c, _ in self.sim.server.commands]


class BackendTests(Base):
    async def test_dial_answer_dtmf_hangup(self):
        await self.backend.dial("0301234")
        self.assertIn(("dial", "sip:0301234@fritz.box"), self.sim.server.commands)
        await self.backend.dtmf("5")
        self.assertIn(("sndcode", "5"), self.sim.server.commands)
        await self.backend.hangup()
        self.assertIn("hangup", self.commands())

    async def test_incoming_call_events_and_ring_repeat(self):
        self.drain()
        await self.sim.server.incoming("+491711234567")
        self.assertTrue(await self.until(lambda: self.q.qsize() >= 4))   # ring, clip, ring …
        evs = self.drain()
        self.assertEqual(evs[:2], [("ring", ""), ("clip", "+491711234567")])
        self.assertIn(("ring", ""), evs[2:])
        self.assertIn("stopringing", self.commands())       # baresip klingelt nicht selbst
        await self.backend.answer()
        self.assertTrue(await self.until(lambda: not self.q.empty()))
        await asyncio.sleep(0.1)
        evs = self.drain()
        self.assertIn(("call_begin", ""), evs)
        self.assertNotIn(("ring", ""), evs[evs.index(("call_begin", "")) + 1:])  # Wiederholung aus
        await self.sim.server.event("CALL_CLOSED", "Connection reset by peer")
        self.assertTrue(await self.until(lambda: not self.q.empty()))
        self.assertEqual(self.drain(), [("call_end", "")])

    async def test_busy_and_anonymous(self):
        self.drain()
        await self.backend.dial("0301234")
        await self.sim.server.event("CALL_CLOSED", "486 Busy Here")
        self.assertTrue(await self.until(lambda: not self.q.empty()))
        self.assertEqual(self.drain(), [("busy", "")])
        await self.sim.server.incoming("")
        self.assertTrue(await self.until(lambda: self.q.qsize() >= 2))
        self.assertEqual(self.drain()[:2], [("ring", ""), ("clip", "")])

    async def test_link_lost_grace_escalation_and_recovery(self):
        self.drain()
        await self.sim.server.set_reachable(False)
        self.assertTrue(await self.until(lambda: not self.backend.online))
        await self.backend.check_link()
        self.assertEqual(self.drain(), [])                  # Schonfrist: noch keine Ansage
        self.t += 11
        await self.backend.check_link()
        self.assertEqual(self.drain(), [("link_lost", "")])
        n_uareg = self.commands().count("uareg")
        with self.assertRaises(ModemError):
            await self.backend.dial("0301234")              # offline: sofort Fehler
        self.t += 50                                        # 61 s weg -> neu registrieren
        await self.backend.check_link()
        self.assertEqual(self.drain(), [])                  # nur einmal ansagen
        self.assertEqual(self.commands().count("uareg"), n_uareg + 1)
        self.t += 5
        await self.backend.check_link()
        self.assertEqual(self.commands().count("uareg"), n_uareg + 1)   # nicht bei jedem Takt
        await self.sim.server.set_reachable(True)
        self.assertTrue(await self.until(lambda: self.backend.online))
        self.assertEqual(self.drain(), [("link_ok", "")])

    async def test_wifi_down_detected_without_waiting_for_sip(self):
        state = Path(self.tmp.name) / "operstate"
        state.write_text("up\n")
        self.backend.operstate_path = str(state)
        await self.backend.check_link()
        self.assertTrue(self.backend.online)
        state.write_text("down\n")
        await self.backend.check_link()
        self.assertFalse(self.backend.online)
        self.assertEqual(self.backend.status_words(), "Keine Verbindung zur Fritzbox.")
        self.assertIsNone(await self.backend.signal())
        self.t += 11
        await self.backend.check_link()
        self.assertIn(("link_lost", ""), self.drain())
        state.write_text("up\n")
        await self.backend.check_link()
        self.assertTrue(self.backend.online)
        self.assertEqual(self.drain(), [("link_ok", "")])

    async def test_baresip_crash_ends_call_and_reconnects(self):
        await self.backend.dial("0301234")
        self.drain()
        await self.sim.server.drop_connection()
        self.assertTrue(await self.until(lambda: not self.backend.connected))
        self.assertIn(("call_end", ""), self.drain())
        await self.backend.check_link()                     # Überwachung verbindet neu
        self.assertTrue(await self.until(lambda: self.backend.online))

    async def test_tam_poll_marks_and_stores_audio(self):
        self.sim.fritz.add_message("01609876543", b"RIFF....WAVEfmt ", "Maria")
        # Der Hintergrundabruf läuft parallel – egal wer zuerst holt: genau einmal.
        await asyncio.gather(self.backend.poll_tam(), self.backend.poll_tam())
        self.assertEqual(await self.backend.poll_tam(), 0)
        evs = [e for e in self.drain() if e[0] == "sms"]
        self.assertEqual(len(evs), 1)
        msg = await self.backend.read_sms(int(evs[0][1]))
        self.assertTrue(Path(msg.audio).exists())
        self.assertEqual(msg.sender, "01609876543")
        self.assertEqual(self.sim.fritz.marked, [0])

    async def test_phonebook_refresh(self):
        self.assertEqual(await self.backend.refresh_phonebook(), 2)
        self.assertEqual(self.cfg.name_for("+4969 90009100"), "Frau Schmidt von nebenan")
        self.sim.fritz.fail = True
        with self.assertRaises(OSError):
            await self.backend.refresh_phonebook()
        self.assertEqual(self.cfg.name_for("06990009100"), "Frau Schmidt von nebenan")  # bleibt


class FestnetzPhoneTests(Base):
    """Phone unverändert benutzt – nur mit dem SIP-Backend."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.cfg.sos_cancel_window_s = 0.05
        self.cfg.emergency_ring_seconds = 0.2
        self.cfg.emergency_rounds = 1
        self.clock = dt.datetime(2026, 11, 1, 18, 21)
        self.audio = SimAudio(self.cfg, echo=False)
        self.hw = SimHardware(self.cfg, self.q, echo=False)
        self.stt = SimRecognizer()
        self.phone = Phone(self.cfg, self.audio, self.backend, self.stt, self.hw, self.q,
                           clock=lambda: self.clock)
        await self.phone.startup()
        self.audio.spoken.clear()

    async def asyncTearDown(self):
        self.phone.cancel_job()
        await super().asyncTearDown()

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

    def said(self):
        return " | ".join(self.audio.spoken)

    async def press(self, key, long=False, held=0.1):
        self.hw.press(key, long, held)
        await self.pump()

    async def test_call_out_and_hang_up(self):
        for d in "0301234":
            await self.press(d)
        await self.press("CALL")
        self.assertTrue(await self.pump_until(lambda: "dial" in self.commands()))
        self.assertIn(("dial", "sip:0301234@fritz.box"), self.sim.server.commands)
        self.sim.inject("call_begin")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.IN_CALL))
        await self.press("HANGUP", held=0.6)
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("hangup", self.commands())

    async def test_incoming_name_from_fritz_phonebook_never_display_name(self):
        await self.backend.refresh_phonebook()
        self.sim.inject_call("06990009100")
        self.assertTrue(await self.pump_until(lambda: "Anruf von" in self.said()))
        self.assertIn("Anruf von Frau Schmidt von nebenan.", self.said())
        self.assertNotIn("Bank", self.said())              # SIP-Anzeigename wird ignoriert
        await self.press("CALL")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.IN_CALL))
        self.assertIn("accept", self.commands())

    async def test_unknown_caller_stays_unknown(self):
        self.sim.inject_call("0301239999")
        self.assertTrue(await self.pump_until(lambda: P["unknown_caller"] in self.said()))
        self.assertNotIn("Bank", self.said())

    async def test_missed_call_when_caller_gives_up(self):
        self.sim.inject_call("+491609876543")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.RINGING))
        self.sim.inject("call_end")
        self.assertTrue(await self.pump_until(lambda: "Verpasster Anruf von Maria." in self.said()))

    async def test_voicemail_is_signalled_then_played_on_key(self):
        self.sim.inject_sms("01609876543")
        self.assertTrue(await self.pump_until(lambda: "<gong>" in self.audio.spoken))
        self.assertNotIn(P["voicemail"], self.said())      # nicht automatisch
        self.assertEqual(self.sim.fritz.marked, [0])
        await self.press("MSG")
        self.assertTrue(await self.pump_until(lambda: any(s.startswith("<abspielen") for s in self.audio.spoken)))
        self.assertIn(f"Neue Nachricht von Maria, heute um 18 Uhr. {P['voicemail']}", self.said())
        played = [s for s in self.audio.spoken if s.startswith("<abspielen")]
        self.assertTrue(played[0].endswith(".wav>"))

    async def test_link_lost_is_announced_and_blocks_dialing_with_feedback(self):
        await self.sim.server.set_reachable(False)
        self.assertTrue(await self.until(lambda: not self.backend.online))
        self.t += 11
        await self.backend.check_link()
        await self.pump()
        self.assertIn(P["link_lost"], self.said())
        self.audio.spoken.clear()
        for d in "0301234":
            await self.press(d)
        await self.press("CALL")
        await self.pump()
        self.assertIn(P["link_lost"], self.said())          # nie stumm
        self.assertNotIn("dial", self.commands())
        await self.press("INFO")
        await self.pump()
        self.assertIn("Keine Verbindung zur Fritzbox.", self.said())
        self.audio.spoken.clear()                            # Erinnerung nach 10 min
        self.clock += dt.timedelta(minutes=10)
        self.q.put_nowait("tick")
        await self.pump()
        self.assertIn(P["link_lost"], self.said())
        await self.sim.server.set_reachable(True)
        self.assertTrue(await self.pump_until(lambda: P["link_ok"] in self.said()))

    async def test_link_lost_at_night_stays_quiet_until_key_or_morning(self):
        self.clock = dt.datetime(2026, 11, 1, 23, 30)
        await self.sim.server.set_reachable(False)
        self.assertTrue(await self.until(lambda: not self.backend.online))
        self.t += 11
        await self.backend.check_link()
        await self.pump()
        self.q.put_nowait("tick")
        await self.pump()
        self.assertNotIn(P["link_lost"], self.said())      # nachts nicht wecken
        await self.press("1")
        await self.press("CALL")
        await self.pump()
        self.assertIn(P["link_lost"], self.said())          # aber auf Tastendruck sofort
        self.audio.spoken.clear()
        self.clock = dt.datetime(2026, 11, 2, 7, 1)          # Ruhezeit vorbei
        self.q.put_nowait("tick")
        await self.pump()
        self.assertIn(P["link_lost"], self.said())

    async def test_sos_chain_ends_with_112_and_pushes_instead_of_sms(self):
        self.cfg.contacts[0].telegram_chat_id = 1     # Peter und Maria per Telegram erreichbar
        self.cfg.contacts[1].telegram_chat_id = 2
        self.q.put_nowait(KeyEvent("SOS", "down"))
        self.q.put_nowait(KeyEvent("SOS", "long"))
        dials = lambda: [p for c, p in self.sim.server.commands if c == "dial"]  # noqa: E731
        self.assertTrue(await self.pump_until(lambda: "sip:112@fritz.box" in dials(), 3000))
        self.assertEqual(dials(), ["sip:+491711234567@fritz.box", "sip:+491609876543@fritz.box",
                                   "sip:+491525550000@fritz.box", "sip:112@fritz.box"])
        self.sim.inject("call_begin")                      # Leitstelle nimmt an
        self.assertTrue(await self.pump_until(lambda: self.phone.call and self.phone.call.answered.is_set()))
        self.sim.inject("call_end")
        self.assertTrue(await self.pump_until(lambda: P["sos_done"] in self.said()))
        sent = {name for name, _, _ in self.sim.notifier.sent}
        self.assertEqual(sent, {"Peter", "Maria"})         # Enkel hat keinen Weg -> nur Log
        self.assertTrue(all("NOTRUF von Oma Erika" in t for _, _, t in self.sim.notifier.sent))

    async def test_lift_answers_and_dock_hangs_up(self):
        self.hw.charging = True
        self.sim.inject_call("+491711234567")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.RINGING))
        self.hw.charging = False
        self.q.put_nowait(KeyEvent("CHARGER", "up"))         # abheben
        await self.pump()
        self.assertTrue(await self.pump_until(lambda: "accept" in self.commands()))
        self.assertEqual(self.phone.state, S.IN_CALL)
        self.assertEqual(self.audio.route_mode, "earpiece")
        self.hw.charging = True
        self.q.put_nowait(KeyEvent("CHARGER", "down"))       # zurück in die Schale
        await self.pump()
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("hangup", self.commands())

    async def test_answer_in_dock_uses_station_speaker(self):
        self.hw.charging = True
        self.sim.inject_call("+491711234567")
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.RINGING))
        await self.press("CALL")                             # Taste statt Abheben
        self.assertEqual(self.audio.route_mode, "speaker")
        self.assertTrue(self.phone.call.speaker)

    async def test_dictation_goes_out_as_push_message(self):
        self.cfg.notify = {"enabled": True}
        self.cfg.contacts[2].telegram_chat_id = 3            # Enkel
        self.stt.answers.put_nowait("enkel")
        self.stt.answers.put_nowait("ich habe die tabletten genommen")
        await self.press("MSG", long=True)
        self.assertTrue(await self.pump_until(lambda: self.phone.state == S.CONFIRM))
        await self.press("CALL")
        self.assertTrue(await self.pump_until(lambda: P["sent"] in self.said()))
        self.assertEqual(self.sim.notifier.sent[-1][0], "der Enkel")

    async def test_dictation_without_route_says_so_before_recording(self):
        self.sim.notifier.enabled = False
        await self.press("MSG", long=True)
        self.assertTrue(await self.pump_until(lambda: P["no_sending"] in self.said()))
        self.assertEqual(self.phone.state, S.IDLE)
        self.sim.notifier.enabled = True
        self.stt.answers.put_nowait("doktor")                # Doktor Weber: keine Chat-ID
        await self.press("MSG", long=True)
        self.assertTrue(await self.pump_until(lambda: P["no_sending_to"] in self.said()))


if __name__ == "__main__":
    unittest.main()
