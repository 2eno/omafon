"""Der echte AT-Treiber (omafon/modem.py) gegen eine nachgebaute serielle Leitung.

Die Leitung antwortet wie ein SIM7600: Befehle mit OK/ERROR, Daten-Zeilen,
'>'-Eingabeaufforderung beim SMS-Senden, unaufgeforderte Meldungen (URCs).
"""
import asyncio
import queue
import sys
import threading
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omafon import pdu
from omafon.modem import Modem, ModemError


class FakeSerial:
    """Antwortet auf Befehle laut `script` (Befehl -> Antwortzeilen)."""
    opened: list["FakeSerial"] = []

    def __init__(self, port, baud, timeout=0.2):
        self.timeout = timeout
        self.out: "queue.Queue[bytes]" = queue.Queue()
        self.cmds: list[str] = []
        self.payloads: list[str] = []
        self.closed = False
        self.waiting_payload = False
        self.script = dict(SCRIPT)
        FakeSerial.opened.append(self)

    def push(self, text: str) -> None:
        self.out.put(text.encode())

    def read(self, n):
        if self.closed:
            raise OSError("geschlossen")
        try:
            return self.out.get(timeout=self.timeout)
        except queue.Empty:
            return b""

    def write(self, data: bytes):
        if self.waiting_payload:                       # PDU nach dem '>'
            self.waiting_payload = False
            self.payloads.append(data.rstrip(b"\x1a").decode())
            self.push(f"\r\n+CMGS: {len(self.payloads)}\r\n\r\nOK\r\n")
            return
        cmd = data.decode().strip()
        self.cmds.append(cmd)
        if cmd.startswith("AT+CMGS="):
            self.waiting_payload = True
            self.push("\r\n> ")
            return
        reply = self.script.get(cmd, self.script.get(cmd.split("=")[0] + "=*", ["OK"]))
        delay = 0.0
        if isinstance(reply, tuple):                   # ("später", Sekunden, Zeilen)
            _, delay, reply = reply
        if reply is not None:
            text = "".join(f"\r\n{line}\r\n" for line in reply)
            if delay:
                threading.Timer(delay, self.push, args=(text,)).start()
            else:
                self.push(text)

    def close(self):
        self.closed = True


(HELLO,) = pdu.build_deliver("+491711234567", "Hallo Oma")
SCRIPT = {
    "AT+CSQ": ["+CSQ: 18,99", "OK"],
    "AT+CMGR=3": ["+CMGR: 0,,25", HELLO, "OK"],
    "AT+CMGR=4": ["OK"],                                 # leer, z. B. verspätetes OK
    "AT+CMGL=4": ["+CMGL: 3,0,,25", HELLO, "+CMGL: 7,0,,25", HELLO, "OK"],
    "AT+VTS=*": ["OK"],
    "AT+CHUP": ["ERROR"],                                # alte Firmware: nur ATH
}


class ModemTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeSerial.opened.clear()
        self._saved = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=FakeSerial)
        self.q = asyncio.Queue()
        self.m = Modem("/dev/null", 115200, self.q, asyncio.get_running_loop())
        await self.m.start()
        self.ser = FakeSerial.opened[-1]

    async def asyncTearDown(self):
        if self.m.ser:
            self.m.ser.close()
        self.m.ser = None                                # Lesethread endet
        if self._saved is None:
            sys.modules.pop("serial", None)
        else:
            sys.modules["serial"] = self._saved

    async def events(self, n, timeout=2.0):
        out = []
        for _ in range(n):
            out.append(await asyncio.wait_for(self.q.get(), timeout))
        return [(e.kind, e.data) for e in out]

    async def test_setup_and_signal(self):
        self.assertIn("AT+CLIP=1", self.ser.cmds)
        self.assertIn("AT+CMGF=0", self.ser.cmds)          # PDU-Modus
        self.assertEqual(await self.m.signal(), 18)

    async def test_read_and_list_sms(self):
        d = await self.m.read_sms(3)
        self.assertEqual((d.sender, d.text), ("+491711234567", "Hallo Oma"))
        self.assertEqual(await self.m.stored_indices(), [3, 7])

    async def test_empty_answer_is_an_error_not_no_sms(self):
        with self.assertRaises(ModemError):                # sonst würde Phone sie löschen
            await self.m.read_sms(4)

    async def test_send_long_sms_in_parts(self):
        await self.m.send_sms("+491711234567", "Gruß " * 60)
        self.assertEqual(len(self.ser.payloads), 2)
        parts = [c for c in self.ser.cmds if c.startswith("AT+CMGS=")]
        self.assertEqual(len(parts), 2)

    async def test_urcs_become_events(self):
        self.ser.push('\r\nRING\r\n\r\n+CLIP: "+491711234567",145,"",0,"",0\r\n')
        self.assertEqual(await self.events(2), [("ring", ""), ("clip", "+491711234567")])
        self.ser.push('\r\n+CMTI: "ME",12\r\n\r\nVOICE CALL: END: 000012\r\nNO CARRIER\r\n')
        evs = await self.events(3)
        self.assertEqual(evs[0], ("sms", "12"))
        self.assertEqual([k for k, _ in evs[1:]], ["call_end", "no_carrier"])

    async def test_gps_position(self):
        self.ser.script["AT+CGPSINFO"] = ["+CGPSINFO: 5030.000000,N,00945.000000,W,061126,120000.0,100.0,0.0,0.0",
                                          "OK"]
        lat, lon = await self.m.gps_position(timeout=2)
        self.assertAlmostEqual(lat, 50.5)
        self.assertAlmostEqual(lon, -9.75)
        self.assertEqual(self.ser.cmds[-1], "AT+CGPS=0")    # GPS danach wieder aus (Akku)

    async def test_no_gps_fix(self):
        self.ser.script["AT+CGPSINFO"] = ["+CGPSINFO: ,,,,,,,,", "OK"]
        self.assertIsNone(await self.m.gps_position(timeout=0.5))

    async def test_network_time(self):
        self.assertIn("AT+CTZU=1", self.ser.cmds)
        self.ser.script["AT+CCLK?"] = ['+CCLK: "26/11/06,12:34:56+04"', "OK"]
        t = await self.m.network_time()
        self.assertEqual((t.year, t.month, t.day), (2026, 11, 6))
        self.ser.script["AT+CCLK?"] = ['+CCLK: "80/01/06,00:00:05+00"', "OK"]   # noch keine Netzzeit
        self.assertIsNone(await self.m.network_time())

    async def test_hangup_falls_back_to_ath(self):
        await self.m.hangup()
        self.assertEqual(self.ser.cmds[-2:], ["AT+CHUP", "ATH"])

    async def test_timeout_is_modem_error(self):
        self.ser.script["AT+CSQ"] = None                   # Modem schweigt
        with self.assertRaises(ModemError):
            await self.m.cmd("AT+CSQ", timeout=0.3)

    async def test_late_answer_does_not_shift_following_commands(self):
        self.ser.script["AT+CSQ"] = ("später", 0.4, ["+CSQ: 18,99", "OK"])
        self.ser.script["AT+CMGR=3"] = ("später", 0.3, ["+CMGR: 0,,25", HELLO, "OK"])
        with self.assertRaises(ModemError):
            await self.m.cmd("AT+CSQ", timeout=0.2)        # Zeitüberschreitung …
        d = await self.m.read_sms(3)                       # … das späte "+CSQ/OK" darf hier nicht
        self.assertEqual(d.text, "Hallo Oma")              # als SMS gelten (sonst gelöscht!)

    async def test_cancelled_command_does_not_shift_following_commands(self):
        self.ser.script["ATD0301234;"] = ("später", 0.3, ["OK"])
        self.ser.script["AT+CSQ"] = ("später", 0.4, ["+CSQ: 18,99", "OK"])
        t = asyncio.create_task(self.m.dial("0301234"))
        await asyncio.sleep(0.05)
        t.cancel()                                          # aufgelegt, während gewählt wird
        with self.assertRaises(asyncio.CancelledError):
            await t
        self.assertEqual(await self.m.signal(), 18)

    async def test_restart_does_not_leave_second_reader(self):
        await self.m.start()                                # Neustart durch Phone
        await asyncio.sleep(0.5)
        readers = [t for t in threading.enumerate() if t.name == "modem-reader" and t.is_alive()]
        self.assertEqual(len(readers), 1)
        self.assertTrue(FakeSerial.opened[0].closed)        # alte Leitung zu
        self.assertEqual(await self.m.signal(), 18)         # neue funktioniert

    async def test_command_before_start(self):
        m = Modem("/dev/null", 115200, asyncio.Queue(), asyncio.get_running_loop())
        with self.assertRaises(ModemError):
            await m.cmd("AT")


if __name__ == "__main__":
    unittest.main()
