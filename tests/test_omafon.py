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
from omafon.modem import SimModem
from omafon.numbers import normalize, spoken_number
from omafon.phone import P, S, Phone
from omafon.stt import SimRecognizer

# Kernlogik mit dem SIM7600-Simulator (Mobilfunkteil des Hybridgeräts)
CFG = Path(__file__).resolve().parents[1] / "config.hybrid.example.yaml"


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

    def test_address_is_cleaned_and_keeps_star_hash(self):
        (s,) = pdu.encode_submit("0171 / 123-45 67", "x")
        self.assertIn(pdu.encode_address("01711234567").hex().upper(), s.pdu_hex)
        self.assertEqual(pdu.decode_address(pdu.encode_address("*31#0171"), 0)[0], "*31#0171")
        with self.assertRaises(ValueError):
            pdu.encode_address("Peter")

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


class WiringDocTests(unittest.TestCase):
    """docs/verkabelung.md muss zur Pinbelegung in hardware.py passen."""

    def test_pinout_matches_code(self):
        import re
        from omafon import hardware as h
        doc = (Path(__file__).resolve().parents[1] / "docs" / "verkabelung.md").read_text(encoding="utf-8")
        names = {"*": "* (Stern)", "#": "# (Raute)", "CALL": "Anrufen (gelb)",
                 "HANGUP": "Auflegen (schwarz)", "MSG": "Nachricht", "INFO": "Info"}
        for bit, key in enumerate(h.MCP_KEYS):
            pin = ("GPA" if bit < 8 else "GPB") + str(bit % 8)
            self.assertRegex(doc, rf"\| {pin} \| {bit} \| {re.escape(names.get(key, key))} \|")
        labels = {"SOS": "SOS-Taster", "SOS_COVER": "Notrufklappe", "VOL_UP": "Lauter",
                  "VOL_DOWN": "Leiser", "CHARGER": "In der Schale"}
        for pin, key, _inv in h.PI_INPUTS:
            self.assertRegex(doc, rf"\| {pin} \| {re.escape(labels[key])} \|")
        for pin, label in ((h.PIN_VIBRA, "Vibration"), (h.PIN_LED, "LED"), (h.PIN_MODEM_PWR, "Modem PWRKEY")):
            self.assertRegex(doc, rf"\| {pin} \| {label}")


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

    async def press(self, key, long=False, held=0.1):
        self.hw.press(key, long, held)
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
        await self.press("HANGUP", held=0.6)               # bewusst gehalten
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("Aufgelegt.", self.said())

    async def test_brief_hangup_in_call_is_ignored(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        await self.press("CALL")
        self.assertEqual(self.phone.state, S.IN_CALL)
        await self.press("HANGUP", held=0.1)               # Wange streift die Taste
        await self.press("HANGUP", held=0.2)
        self.assertEqual(self.phone.state, S.IN_CALL)
        self.assertEqual(self.said().count(P["hangup_hold"]), 1)   # Hinweis nur einmal
        self.assertNotIn("AT+CHUP", self.modem.log)
        await self.press("HANGUP", long=True)              # lang gedrückt: aufgelegt
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("AT+CHUP", self.modem.log)

    async def test_hangup_hold_can_be_switched_off(self):
        self.cfg.hangup_hold_s = 0
        self.modem.inject_call("+491711234567")
        await self.pump()
        await self.press("CALL")
        await self.press("HANGUP", held=0.05)
        self.assertEqual(self.phone.state, S.IDLE)

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

    async def test_sms_is_signalled_not_read(self):
        self.modem.inject_sms("+491609876543", "Ich komme morgen um drei vorbei.")
        await self.pump()
        self.assertEqual(self.audio.spoken, ["<gong>"])    # nur Signal, kein Vorlesen
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertEqual(self.modem.store, {})            # aus dem Modem gelöscht
        await self.press("MSG")                            # erst auf Tastendruck vorlesen
        self.assertIn("Neue Nachricht von Maria, heute um 18 Uhr.", self.said())
        self.assertIn("Ich komme morgen um drei vorbei.", self.said())
        self.assertEqual(self.phone.state, S.READING)
        await self.press("CALL")                           # zurückrufen
        self.assertIn("ATD+491609876543;", self.modem.log)

    async def test_signal_repeats_and_led_blinks_until_read(self):
        self.modem.inject_sms("+491609876543", "Hallo")
        await self.pump()
        self.assertEqual(self.audio.spoken.count("<gong>"), 1)
        for _ in range(4):                                 # 1 s an, 2 s aus
            self.q.put_nowait("tick")
            await self.pump(2)
        self.assertIn("LED an", self.hw.log)
        self.assertIn("LED aus", self.hw.log)
        self.clock += dt.timedelta(minutes=5)
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.audio.spoken.count("<gong>"), 1)  # noch nicht fällig
        self.clock += dt.timedelta(minutes=5)
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.audio.spoken.count("<gong>"), 2)  # Erinnerung nach 10 min
        await self.press("MSG")
        await self.press("HANGUP")                         # gelesen, zurück in Ruhe
        self.hw.log.clear()
        self.clock += dt.timedelta(minutes=30)
        for _ in range(3):
            self.q.put_nowait("tick")
            await self.pump(2)
        self.assertEqual(self.audio.spoken.count("<gong>"), 2)  # keine Erinnerung mehr
        self.assertNotIn("LED an", self.hw.log)
        self.assertFalse(self.hw.led)

    async def test_long_sms_reassembled(self):
        text = "Hallo Mama, " + "das Wetter ist schön und wir denken an dich. " * 8
        self.modem.inject_sms("+491711234567", text)
        await self.pump()
        self.assertEqual(self.phone.inbox[0]["text"], text.strip())
        self.assertEqual(self.audio.spoken.count("<gong>"), 1)   # ein Signal, nicht pro Teil
        await self.press("MSG")
        self.assertEqual(self.said().count("Nachricht von Peter"), 1)

    async def test_sms_during_call_is_signalled_afterwards(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        await self.press("CALL")
        self.modem.inject_sms("+491609876543", "Bis gleich")
        await self.pump()
        self.assertNotIn("<gong>", self.audio.spoken)     # kein Gong ins Gespräch
        self.modem.inject("call_end")
        await self.pump()
        self.q.put_nowait("tick")
        await self.pump()
        self.assertIn("<gong>", self.audio.spoken)        # danach angekündigt …
        self.assertNotIn("Bis gleich", self.said())        # … aber nicht vorgelesen

    async def test_quiet_hours_only_led(self):
        self.clock = dt.datetime(2026, 11, 1, 23, 5)
        self.modem.inject_sms("+491609876543", "Gute Nacht")
        for _ in range(3):
            self.q.put_nowait("tick")
            await self.pump(2)
        self.assertNotIn("<gong>", self.audio.spoken)     # nachts kein Ton
        self.assertIn("LED an", self.hw.log)
        self.clock = dt.datetime(2026, 11, 2, 7, 0)        # Ruhezeit vorbei
        self.q.put_nowait("tick")
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

    async def test_sms_arriving_while_reading_keeps_position(self):
        self.modem.inject_sms("+491711234567", "Erste von Peter")
        self.modem.inject_sms("+491609876543", "Zweite von Maria")
        await self.pump()
        await self.press("MSG")
        self.assertIn("Erste von Peter", self.said())
        self.modem.inject_sms("+491525550000", "Neu vom Enkel")   # rückt im Posteingang vorn ein
        await self.pump()
        await self.press("CALL")                                  # zurückrufen: immer noch Peter
        self.assertIn("ATD+491711234567;", self.modem.log)

    async def test_sos_while_ringing_stops_ringing(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        self.assertIsNotNone(self.phone.ring_task)
        self.phone.on_sos_key("SOS", "long")
        await self.pump_until(lambda: self.phone.state == S.SOS)
        await self.pump()
        self.assertIsNone(self.phone.ring_task)
        self.assertIn("AT+CHUP", self.modem.log)                 # Anruf abgewiesen
        await self.press("HANGUP")                                 # Notruf abbrechen

    async def test_restart_waits_if_call_comes_during_announcement(self):
        self.phone.pause_s = 0.05
        self.phone.request_restart("settings_restart")
        self.modem.inject_call("+491711234567")
        await self.pump(40)
        self.assertFalse(self.phone.restart_event.is_set())      # nie während es klingelt
        self.assertEqual(self.phone.restart_reason, "settings_restart")

    async def test_dead_modem_is_announced_once_then_retried_quietly(self):
        self.modem.fail_alive = True
        for _ in range(3):
            await self.phone.check_modem()
        await self.pump(2)
        self.assertEqual(self.said().count(P["modem_dead"]), 1)
        self.assertIn("Modem neu gestartet", self.hw.log)
        for _ in range(9):                                         # weitere Minuten: still
            await self.phone.check_modem()
        await self.pump(2)
        self.assertEqual(self.said().count(P["modem_restart"]), 1)
        self.clock += dt.timedelta(minutes=31)
        self.modem.fail_alive = False
        await self.phone.check_modem()
        await self.pump(2)
        self.assertIn(P["network_ok"], self.said())

    async def test_missed_calls_list_is_bounded(self):
        for i in range(25):
            self.phone.call = None
            self.modem.inject_call(f"+4930123{i:03}")
            await self.pump(2)
            self.modem.inject("missed")
            await self.pump(2)
        self.assertEqual(len(self.phone.missed), 20)

    async def test_older_message_header_has_single_full_stop(self):
        self.clock = dt.datetime(2026, 11, 5, 15, 0)
        self.modem.inject_sms("+491711234567", "Alt")               # Zeitstempel 1.11.
        await self.pump()
        await self.press("MSG")
        self.assertIn("Neue Nachricht von Peter, am 1. 11. Alt", self.said())
        self.assertNotIn("..", self.said())

    async def test_brief_sos_press_during_call_keeps_call(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        await self.press("CALL")
        self.assertEqual(self.phone.state, S.IN_CALL)
        self.assertEqual(self.audio.route_mode, "earpiece")
        self.phone.on_sos_key("SOS", "down")                   # Knopf aus Versehen gestreift
        await self.pump(3)
        self.phone.on_sos_key("SOS", "short")
        await self.pump()
        self.assertEqual(self.phone.state, S.IN_CALL)           # Gespräch läuft weiter …
        self.assertEqual(self.audio.route_mode, "earpiece")     # … am Ohr, nicht laut
        await self.press("HANGUP", held=0.6)                    # und lässt sich auflegen
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("AT+CHUP", self.modem.log)

    async def test_brief_sos_press_while_ringing_keeps_ringing(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        self.phone.on_sos_key("SOS", "down")
        await self.pump(3)
        self.phone.on_sos_key("SOS", "short")
        await self.pump()
        self.assertEqual(self.phone.state, S.RINGING)
        await self.press("CALL")
        self.assertEqual(self.phone.state, S.IN_CALL)

    async def test_failed_dial_does_not_block_incoming_calls(self):
        self.modem.csq = 0                                      # Wählen scheitert
        await self.press("1", long=True)                        # Kurzwahl
        await self.pump_until(lambda: P["not_reached"] in self.said())
        self.assertIsNone(self.phone.call)
        self.modem.csq = 22
        self.modem.inject_call("+491609876543")
        await self.pump()
        self.assertEqual(self.phone.state, S.RINGING)           # klingelt wieder

    async def test_ring_timeout_releases_backend(self):
        self.modem.inject("ring")
        await self.pump()
        self.clock += dt.timedelta(seconds=9)                   # Klingeln hört ohne Meldung auf
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.phone.state, S.IDLE)
        self.assertIn("AT+CHUP", self.modem.log)

    async def test_volume_restored_after_emergency(self):
        self.audio.set_volume(2)
        self.phone.state = S.SOS
        self.phone.loud_for_emergency()
        self.assertEqual(self.audio.volume, 5)
        self.phone.callback_until = self.clock + dt.timedelta(minutes=30)
        self.phone.go_idle()
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.audio.volume, 5)                  # Rückrufzeit: noch laut
        self.clock += dt.timedelta(minutes=31)
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.audio.volume, 2)

    async def test_hangup_is_announced_before_slow_modem_answers(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        await self.press("CALL")
        hang = asyncio.Event()

        async def slow_hangup():
            await hang.wait()                                     # Modem hängt
        self.modem.hangup = slow_hangup
        self.hw.press("HANGUP", held=0.6)
        task = asyncio.create_task(self.pump(5))
        await asyncio.sleep(0.05)
        self.assertIn(P["hung_up"], self.said())                  # Regel 1: sofort
        self.assertEqual(self.phone.state, S.IDLE)
        hang.set()
        await task

    async def test_sms_not_deleted_when_modem_answers_empty(self):
        self.modem.inject_sms("+491711234567", "Wichtig")
        real_read = self.modem.read_sms
        from omafon.modem import ModemError as ME

        async def empty_read(i):
            raise ME("keine Daten")                               # verspätetes OK o. Ä.
        self.modem.read_sms = empty_read
        await self.pump()
        self.assertEqual(self.phone.inbox, [])
        self.assertEqual(len(self.modem.store), 1)                # liegt noch auf der SIM
        self.modem.read_sms = real_read
        self.phone.ticks = 599                                    # 10 Minuten später, in Ruhe
        self.q.put_nowait("tick")
        await self.pump()
        self.assertEqual(self.phone.inbox[0]["text"], "Wichtig")
        self.assertEqual(self.modem.store, {})

    def test_texts_are_in_p_dict(self):
        """Regel 3: feste Ansagen nur in P (sonst fehlen sie im WAV-Cache)."""
        import re
        src = (Path(__file__).resolve().parents[1] / "omafon" / "phone.py").read_text(encoding="utf-8")
        body = src.split("class Phone", 1)[1]
        fixed = re.findall(r'(?:say|speak)\("([^"{]+)"\)', body)
        self.assertEqual(fixed, [], f"Feste Texte außerhalb von P: {fixed}")


class ConfigTests(unittest.TestCase):
    def load_with(self, extra: str):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(CFG.read_text(encoding="utf-8") + "\n" + extra + "\n")
        try:
            return config.load(f.name)
        finally:
            Path(f.name).unlink()

    def test_bad_values_fail_at_start_with_clear_message(self):
        for extra, word in (("quiet_hours: [22]", "quiet_hours"), ("volume: 9", "volume"),
                            ("emergency_ring_seconds: dreißig", "emergency_ring_seconds"),
                            ("default_route: laut", "default_route"),
                            ("home_position: [51]", "home_position")):
            with self.subTest(extra=extra), self.assertRaises(ValueError) as e:
                self.load_with(extra)
            self.assertIn(word, str(e.exception))

    def test_duplicate_speed_dial(self):
        cfg = config.load(CFG)
        cfg.contacts[1].speed_dial = cfg.contacts[0].speed_dial
        with self.assertRaises(ValueError):
            config.validate(cfg)


class HardwareTests(unittest.IsolatedAsyncioTestCase):
    """Regel 2: fällt der MCP23017 aus (auch schon beim Start), geht der Notruf."""

    async def test_sos_works_without_i2c(self):
        import types
        pressed = {"SOS": False}

        class Button:
            def __init__(self, pin, pull_up=True, bounce_time=None):
                self.pin = pin

            @property
            def is_pressed(self):
                return self.pin == 22 and pressed["SOS"]

        class Out:
            def __init__(self, pin): self.value = 0
            def on(self): pass
            def off(self): pass

        class DeadBus:
            def __init__(self, n): pass
            def write_byte_data(self, *a): raise OSError(121, "Remote I/O error")
            def read_byte_data(self, *a): raise OSError(121, "Remote I/O error")
            def read_i2c_block_data(self, *a): raise OSError(121, "Remote I/O error")

        fake = {"gpiozero": types.SimpleNamespace(Button=Button, DigitalOutputDevice=Out,
                                                   PWMOutputDevice=Out),
                "smbus2": types.SimpleNamespace(SMBus=DeadBus)}
        saved = {k: sys.modules.get(k) for k in fake}
        sys.modules.update(fake)
        try:
            from omafon.hardware import Hardware
            cfg = config.load(CFG)
            cfg.sos_hold_s = 0.2
            q = asyncio.Queue()
            hw = Hardware(cfg, q, asyncio.get_running_loop())   # darf nicht abstürzen
            self.addCleanup(hw.close)
            self.assertFalse(hw.mcp_ok)
            self.assertIsNone(hw.battery_percent())
            pressed["SOS"] = True
            kinds = []
            for _ in range(100):
                await asyncio.sleep(0.01)
                while not q.empty():
                    ev = q.get_nowait()
                    if ev.key == "SOS":
                        kinds.append(ev.kind)
                if "long" in kinds:
                    break
            self.assertEqual(kinds[:2], ["down", "long"])
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


class AudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_newer_announcement_drops_queued_ones(self):
        from omafon.audio import Audio
        with tempfile.TemporaryDirectory() as d:
            cfg = config.load(CFG)
            cfg.cache_dir = d
            audio = Audio(cfg)
            started = []

            class Proc:
                returncode = None
                async def wait(self):
                    await asyncio.sleep(0.05)
                    self.returncode = 0
                def terminate(self): self.returncode = -15
                def kill(self): pass

            async def fake_exec(*cmd, **kw):
                started.append(cmd[-1])
                return Proc()

            orig = asyncio.create_subprocess_exec
            asyncio.create_subprocess_exec = fake_exec
            try:
                async def synth(text):
                    return Path(d) / f"{text}.wav"
                audio.synth = synth
                first = asyncio.create_task(audio.say("eins"))
                await asyncio.sleep(0.01)
                queued = [asyncio.create_task(audio.say(w, interrupt=False)) for w in ("zwo", "drei")]
                await asyncio.sleep(0.01)
                await audio.say("Abgebrochen.")               # unterbricht – Rest entfällt
                await asyncio.gather(first, *queued)
            finally:
                asyncio.create_subprocess_exec = orig
            names = [Path(p).stem for p in started]
            self.assertEqual(names[0], "eins")
            self.assertEqual(names[-1], "Abgebrochen.")
            self.assertNotIn("drei", names)

    async def test_missing_player_does_not_crash(self):
        from omafon.audio import Audio
        with tempfile.TemporaryDirectory() as d:
            cfg = config.load(CFG)
            cfg.cache_dir = d

            async def no_exec(*a, **k):
                raise FileNotFoundError("aplay")
            orig = asyncio.create_subprocess_exec
            asyncio.create_subprocess_exec = no_exec
            try:
                audio = Audio(cfg)
                with self.assertLogs("omafon.audio", "ERROR"):
                    await audio.play(Path(d) / "x.wav")
            finally:
                asyncio.create_subprocess_exec = orig


if __name__ == "__main__":
    unittest.main()
