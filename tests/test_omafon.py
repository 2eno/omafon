"""Tests ohne Hardware:  python3 -m unittest discover -s tests -v"""
import asyncio
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omafon import config, pdu
from omafon.audio import SimAudio
from omafon.hardware import KeyEvent, KeyTracker, SimHardware
from omafon.modem import ModemEvent, SimModem
from omafon.numbers import normalize, spoken_number
from omafon.phone import P, S, Phone
from omafon.stt import SimRecognizer

CFG = Path(__file__).resolve().parents[1] / "config.example.yaml"


class PduTests(unittest.TestCase):
    def test_classic_example(self):
        # Bekanntes Beispiel aus der GSM-Literatur: "hellohello"
        d = pdu.decode_deliver("07917283010010F5040BC87238880900F10000993092516195800AE8329BFD4697D9EC37")
        self.assertEqual(d.text, "hellohello")
        self.assertEqual(d.sender, "27838890001")

    def test_gsm7_roundtrip_with_umlauts_and_euro(self):
        text = "Hallo Oma, wie geht's? Äpfel für 5€ – nein, Spaß: [ok]"
        text = text.replace("–", "-")
        (p,) = pdu.build_deliver("+491711234567", text)
        d = pdu.decode_deliver(p)
        self.assertEqual(d.text, text)
        self.assertEqual(d.sender, "+491711234567")
        self.assertIsNone(d.concat_ref)

    def test_ucs2_emoji(self):
        text = "Liebe Grüße 😘 bis Sonntag"
        (p,) = pdu.build_deliver("+491711234567", text)
        self.assertEqual(pdu.decode_deliver(p).text, text)

    def test_long_messages_are_split_and_tagged(self):
        long7 = "Das ist ein langer Text. " * 20            # 500 Zeichen GSM-7
        parts = [pdu.decode_deliver(p) for p in pdu.build_deliver("+4917012", long7)]
        self.assertEqual(len(parts), 4)
        self.assertEqual("".join(p.text for p in parts), long7)
        self.assertEqual({p.concat_total for p in parts}, {4})
        longu = "Grüße 😀 " * 30                              # UCS-2, mehrteilig
        parts = [pdu.decode_deliver(p) for p in pdu.build_deliver("+4917012", longu)]
        self.assertGreater(len(parts), 1)
        self.assertEqual("".join(p.text for p in parts), longu)

    def test_submit_lengths(self):
        (s,) = pdu.encode_submit("+491711234567", "Test")
        self.assertEqual(s.tpdu_len, len(bytes.fromhex(s.pdu_hex)) - 1)
        self.assertEqual(len(pdu.encode_submit("+49171", "x" * 160)), 1)
        self.assertEqual(len(pdu.encode_submit("+49171", "x" * 161)), 2)
        self.assertEqual(len(pdu.encode_submit("+49171", "ü" * 160)), 1)   # ü ist GSM-7
        self.assertEqual(len(pdu.encode_submit("+49171", "😀" * 35)), 1)   # 70 UTF-16-Einheiten
        self.assertEqual(len(pdu.encode_submit("+49171", "😀" * 36)), 2)


class NumberTests(unittest.TestCase):
    def test_spoken(self):
        self.assertEqual(spoken_number("01712"), "null eins sieben, eins zwo")
        self.assertTrue(spoken_number("01711234567").startswith("null eins sieben eins, eins zwo drei"))

    def test_normalize(self):
        self.assertEqual(normalize("+49 171 123"), "0171123")
        self.assertEqual(normalize("0049171123"), "0171123")


class KeyTrackerTests(unittest.TestCase):
    def test_debounce_short_long(self):
        evs = []
        kt = KeyTracker(evs.append, long_s=1.2)
        t = 0.0
        for pressed in (True, False, True, False):        # Prellen innerhalb 30 ms
            kt.update("5", pressed, t)
            t += 0.01
        kt.update("5", False, t + 0.2)
        self.assertEqual(evs, [])                          # nichts ausgelöst
        kt.update("5", True, 1.0)
        kt.update("5", True, 1.1)
        kt.update("5", False, 1.3)
        kt.update("5", False, 1.4)
        self.assertEqual([e.kind for e in evs], ["down", "short", "up"])
        evs.clear()
        for i in range(160):
            kt.update("CALL", True, 2.0 + i * 0.01)
        kt.update("CALL", False, 4.0)
        kt.update("CALL", False, 4.1)
        self.assertEqual([e.kind for e in evs], ["down", "long", "up"])


class PhoneTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = config.load(CFG)
        self.cfg.data_dir = self.tmp.name
        self.cfg.sos_cancel_window_s = 0.05
        self.cfg.emergency_ring_seconds = 0.2
        self.cfg.emergency_rounds = 1
        self.clock = dt.datetime(2026, 11, 1, 18, 21)
        self.q = asyncio.Queue()
        self.audio = SimAudio(self.cfg, echo=False)
        self.modem = SimModem(self.q, echo=False)
        self.hw = SimHardware(self.cfg, self.q, echo=False)
        self.stt = SimRecognizer()
        self.phone = Phone(self.cfg, self.audio, self.modem, self.stt, self.hw, self.q,
                           clock=lambda: self.clock)
        await self.phone.startup()
        self.audio.spoken.clear()

    async def asyncTearDown(self):
        self.phone.cancel_job()
        self.tmp.cleanup()

    async def pump(self, rounds=30):
        for _ in range(rounds):
            while not self.q.empty():
                await self.phone.handle(self.q.get_nowait())
            await asyncio.sleep(0.005)

    async def pump_until(self, cond, max_rounds=1000):
        for _ in range(max_rounds):
            if cond():
                return True
            await self.pump(1)
        return False

    def said(self):
        return " | ".join(self.audio.spoken)

    async def press(self, key, long=False):
        self.hw.press(key, long)
        await self.pump()

    async def test_digits_are_echoed_and_dialed(self):
        for d in "01711234567":
            await self.press(d)
        self.assertEqual(self.audio.spoken[:3], ["null", "eins", "sieben"])
        self.assertIn("zwo", self.audio.spoken)
        await self.press("CALL")
        self.assertIn("Ich rufe Peter an.", self.said())
        self.assertIn("ATD01711234567;", self.modem.log)
        self.assertEqual(self.phone.state, S.OUTGOING)
        self.modem.inject("call_begin")
        await self.pump()
        self.assertEqual(self.phone.state, S.IN_CALL)
        await self.press("HANGUP")
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("Aufgelegt.", self.said())

    async def test_backspace_and_timeout(self):
        await self.press("4")
        await self.press("2")
        await self.press("HANGUP")
        self.assertEqual(self.phone.number, "4")
        self.clock += dt.timedelta(seconds=25)
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn(P["entry_cleared"], self.said())

    async def test_speed_dial(self):
        await self.press("2", long=True)
        self.assertIn("Ich rufe Maria an.", self.said())
        self.assertIn("ATD+491609876543;", self.modem.log)

    async def test_incoming_call_answered(self):
        self.modem.inject_call("+491711234567")
        await self.pump(80)
        self.assertEqual(self.phone.state, S.RINGING)
        self.assertIn("Anruf von Peter.", self.said())
        await self.press("CALL")
        self.assertIn("ATA", self.modem.log)
        self.assertEqual(self.phone.state, S.IN_CALL)
        self.modem.inject("call_end")
        await self.pump()
        self.assertIn(P["call_ended"], self.said())

    async def test_missed_call_then_info(self):
        self.modem.inject_call("+491609876543")
        await self.pump()
        self.modem.inject("no_carrier")
        await self.pump()
        self.assertIn("Verpasster Anruf von Maria.", self.said())
        await self.press("INFO")
        self.assertIn("Es ist 18 Uhr 21.", self.said())
        self.assertIn("Ein verpasster Anruf von Maria.", self.said())
        self.assertIn("Akku 80 Prozent.", self.said())

    async def test_sms_is_read_automatically(self):
        self.modem.inject_sms("+491609876543", "Ich komme morgen um drei vorbei.")
        await self.pump()
        self.assertIn("Neue Nachricht. Von Maria, heute um 18 Uhr.", self.said())
        self.assertIn("Ich komme morgen um drei vorbei.", self.said())
        self.assertEqual(self.phone.state, S.READING)
        self.assertEqual(self.modem.store, {})            # aus dem Modem gelöscht
        await self.press("CALL")                           # zurückrufen
        self.assertIn("ATD+491609876543;", self.modem.log)

    async def test_long_sms_reassembled(self):
        text = "Hallo Mama, " + "das Wetter ist schön und wir denken an dich. " * 8
        self.modem.inject_sms("+491711234567", text)
        await self.pump()
        self.assertEqual(self.phone.inbox[0]["text"], text.strip())
        self.assertEqual(self.said().count("Von Peter"), 1)

    async def test_sms_during_call_is_read_afterwards(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        await self.press("CALL")
        self.modem.inject_sms("+491609876543", "Bis gleich")
        await self.pump()
        self.assertNotIn("Bis gleich", self.said())
        self.modem.inject("call_end")
        await self.pump()
        self.q.put_nowait("tick")
        await self.pump()
        self.assertIn("Bis gleich", self.said())

    async def test_quiet_hours_only_gong(self):
        self.clock = dt.datetime(2026, 11, 1, 23, 5)
        self.modem.inject_sms("+491609876543", "Gute Nacht")
        await self.pump()
        self.assertIn("<gong>", self.audio.spoken)
        self.assertNotIn("Gute Nacht", self.said())

    async def test_voice_dial(self):
        self.stt.answers.put_nowait("tochter")
        await self.press("CALL")
        await self.pump()
        self.assertIn("Maria. Gelbe Taste zum Anrufen.", self.said())
        await self.press("CALL")
        self.assertIn("ATD+491609876543;", self.modem.log)

    async def test_dictate_and_send(self):
        self.stt.answers.put_nowait("enkel")
        self.stt.answers.put_nowait("ich habe die tabletten genommen")
        await self.press("MSG", long=True)
        await self.pump()
        self.assertEqual(self.phone.state, S.CONFIRM)
        self.assertIn("Ich habe die tabletten genommen.", self.said())
        await self.press("CALL")
        await self.pump()
        self.assertEqual(self.modem.sent, [("+491525550000", "Ich habe die tabletten genommen.")])
        self.assertIn(P["sent"], self.said())

    async def test_sos_released_too_early(self):
        q = self.q.put_nowait
        q(KeyEvent("SOS", "down"))
        q(KeyEvent("SOS", "short"))
        await self.pump()
        self.assertIn(P["cancelled"], self.said())
        self.assertEqual(self.modem.sent, [])

    async def test_sos_chain(self):
        self.q.put_nowait(KeyEvent("SOS_COVER", "down"))
        await self.pump()
        self.assertIn(P["sos_cover"], self.said())
        self.q.put_nowait(KeyEvent("SOS", "down"))
        self.q.put_nowait(KeyEvent("SOS", "long"))
        await self.pump(40)
        self.assertIn("ATD+491711234567;", self.modem.log)     # Peter geht nicht ran
        self.assertTrue(await self.pump_until(                  # nach 2 s Pause: Maria
            lambda: "ATD+491609876543;" in self.modem.log))
        self.modem.inject("call_begin")
        await self.pump()
        self.modem.inject("call_end")
        await self.pump(20)
        self.assertIn(P["sos_done"], self.said())
        sms_to = {n for n, _ in self.modem.sent}
        self.assertEqual(sms_to, {"+491711234567", "+491609876543", "+491525550000"})
        self.assertTrue(any("openstreetmap" in t for _, t in self.modem.sent))
        # Rückruf von Peter wird automatisch angenommen
        self.modem.inject_call("+491711234567")
        await self.pump()
        self.assertEqual(self.modem.log[-1], "ATA")
        self.assertEqual(self.phone.state, S.IN_CALL)

    async def test_admin_status_sms(self):
        self.modem.inject_sms("+491525550000", "status")
        await self.pump()
        self.assertEqual(len(self.modem.sent), 1)
        self.assertTrue(self.modem.sent[0][1].startswith("Omafon: Akku 80%"))
        self.assertEqual(self.phone.inbox, [])


if __name__ == "__main__":
    unittest.main()
