"""AT driver for the SIMCom SIM7600 (A7670 very similar).

A reader thread separates answers to commands from unsolicited messages
(URCs like RING, +CLIP, +CMTI). URCs end up as ModemEvent in the phone's
event queue.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from . import pdu
from .telephony import ModemError, ModemEvent, TelephonyBackend

__all__ = ["Modem", "SimModem", "ModemEvent", "ModemError"]

log = logging.getLogger("omafon.modem")


URC_PREFIXES = {
    "RING": "ring", "+CLIP:": "clip", "+CMTI:": "sms",
    "VOICE CALL: BEGIN": "call_begin", "VOICE CALL: END": "call_end",
    "NO CARRIER": "no_carrier", "BUSY": "busy", "NO ANSWER": "no_answer",
    "MISSED_CALL:": "missed",
}
IGNORED_URCS = ("+CPIN:", "SMS DONE", "PB DONE", "RDY", "+CGEV:", "+CREG:", "+CEREG:")


class Modem(TelephonyBackend):
    """Mobile part of the hybrid device: SIM7600 with SMS and GPS."""
    name = "sim7600"
    supports_sms = True

    def __init__(self, port: str, baud: int, events: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.port, self.baud = port, baud
        self.events, self.loop = events, loop
        self.ser = None
        self._lock = asyncio.Lock()           # only one command at a time
        self._resp: list[str] = []
        self._done = threading.Event()
        self._prompt = threading.Event()
        self._error: str | None = None
        self._prefix = ""
        self._busy = False
        self._ref = 0

    # ------------------------------------------------------------ Connection
    async def start(self) -> None:
        import serial  # pyserial
        self.ser = serial.Serial(self.port, self.baud, timeout=0.2)
        threading.Thread(target=self._reader, daemon=True, name="modem-reader").start()
        for _ in range(20):
            try:
                await self.cmd("AT", timeout=1)
                break
            except ModemError:
                await asyncio.sleep(1)
        else:
            raise ModemError("Modem antwortet nicht")
        for c in ("ATE0", "AT+CMEE=2", "AT+CLIP=1", "AT+CMGF=0",
                  'AT+CPMS="ME","ME","ME"', "AT+CNMI=2,1,0,0,0", "AT+CLVL=4"):
            try:
                await self.cmd(c)
            except ModemError as e:
                log.warning("%s -> %s", c, e)

    def _emit(self, ev: ModemEvent) -> None:
        log.info("URC %s %s", ev.kind, ev.data)
        self.loop.call_soon_threadsafe(self.events.put_nowait, ev)

    def _reader(self) -> None:
        buf = b""
        while True:
            try:
                chunk = self.ser.read(256)
            except Exception as e:  # cable unplugged, modem reset …
                log.error("Serial port: %s", e)
                time.sleep(1)
                continue
            if not chunk:
                if self._busy and buf.strip() == b">":
                    self._prompt.set()
                continue
            buf += chunk
            if self._busy and buf.lstrip().startswith(b">"):
                self._prompt.set()
                buf = buf.lstrip()[1:]
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._line(line)

    def _line(self, line: str) -> None:
        if self._busy:
            if line == "OK":
                self._done.set()
                return
            if line == "ERROR" or line.startswith(("+CME ERROR", "+CMS ERROR")):
                self._error = line
                self._done.set()
                return
            if self._prefix and line.startswith(self._prefix):
                self._resp.append(line)
                return
        for prefix, kind in URC_PREFIXES.items():
            if line.startswith(prefix):
                data = line[len(prefix):].strip(" :")
                if kind == "clip":
                    data = data.split(",")[0].strip('"')
                elif kind == "sms":
                    data = data.split(",")[-1]
                self._emit(ModemEvent(kind, data))
                if self._busy and kind in ("no_carrier", "busy", "no_answer"):
                    self._error = line
                    self._done.set()
                return
        if line.startswith(IGNORED_URCS):
            return
        if self._busy:
            self._resp.append(line)   # e.g. the PDU line after +CMGR
        else:
            log.debug("unknown: %s", line)

    # ------------------------------------------------------------ Commands
    async def cmd(self, command: str, timeout: float = 5, prefix: str | None = None,
                  payload: str | None = None) -> list[str]:
        """Sends an AT command. payload: data after the '>' prompt (SMS)."""
        async with self._lock:
            self._resp, self._error = [], None
            self._done.clear()
            self._prompt.clear()
            self._prefix = prefix if prefix is not None else (
                command[2:].split("=")[0].split("?")[0] if command.startswith("AT+") else "")
            self._busy = True
            try:
                log.debug(">> %s", command)
                self.ser.write((command + "\r").encode())
                if payload is not None:
                    ok = await self.loop.run_in_executor(None, self._prompt.wait, 10)
                    if not ok:
                        self.ser.write(b"\x1b")
                        raise ModemError("kein Eingabe-Prompt")
                    self.ser.write(payload.encode() + b"\x1a")
                ok = await self.loop.run_in_executor(None, self._done.wait, timeout)
                if not ok:
                    raise ModemError(f"Zeitüberschreitung: {command}")
                if self._error:
                    raise ModemError(self._error)
                return list(self._resp)
            finally:
                self._busy = False

    # ------------------------------------------------------------ Telephony
    async def dial(self, number: str) -> None:
        await self.cmd(f"ATD{number};", timeout=20)

    async def answer(self) -> None:
        await self.cmd("ATA", timeout=10)

    async def hangup(self) -> None:
        try:
            await self.cmd("AT+CHUP", timeout=10)
        except ModemError:
            await self.cmd("ATH", timeout=10)

    async def dtmf(self, digit: str) -> None:
        await self.cmd(f"AT+VTS={digit}")

    async def call_volume(self, level: int) -> None:
        await self.cmd(f"AT+CLVL={max(0, min(5, level))}")

    async def set_radio(self, on: bool) -> None:
        """Radio on (CFUN=1) or off (CFUN=4, airplane mode) – for the hybrid power saving."""
        await self.cmd(f"AT+CFUN={1 if on else 4}", timeout=15)

    # ------------------------------------------------------------ SMS
    async def read_sms(self, index: int) -> pdu.Deliver | None:
        lines = await self.cmd(f"AT+CMGR={index}", prefix="+CMGR")
        hexline = next((l for l in lines if not l.startswith("+CMGR")), None)
        if not hexline:
            return None
        try:
            return pdu.decode_deliver(hexline)
        except (ValueError, IndexError) as e:
            log.error("PDU not readable (%s): %s", e, hexline)
            return None

    async def delete_sms(self, index: int) -> None:
        await self.cmd(f"AT+CMGD={index}")

    async def stored_indices(self) -> list[int]:
        """All stored SMS (e.g. received while the phone was off)."""
        lines = await self.cmd("AT+CMGL=4", prefix="+CMGL", timeout=20)
        return [int(l.split(":")[1].split(",")[0]) for l in lines if l.startswith("+CMGL")]

    async def send_sms(self, number: str, text: str) -> None:
        self._ref = (self._ref + 1) % 256
        for part in pdu.encode_submit(number, text, self._ref):
            await self.cmd(f"AT+CMGS={part.tpdu_len}", timeout=60,
                           prefix="+CMGS", payload=part.pdu_hex)

    # ------------------------------------------------------------ Status
    async def signal(self) -> int | None:
        try:
            line = (await self.cmd("AT+CSQ"))[0]
            return int(line.split(":")[1].split(",")[0])
        except (ModemError, IndexError, ValueError):
            return None

    async def alive(self) -> bool:
        try:
            await self.cmd("AT", timeout=2)
            return True
        except ModemError:
            return False

    async def gps_position(self, timeout: float = 30) -> tuple[float, float] | None:
        """One-off location fix for the emergency call. Often no result indoors."""
        try:
            await self.cmd("AT+CGPS=1")
        except ModemError:
            pass  # may already be running
        end = time.monotonic() + timeout
        try:
            while time.monotonic() < end:
                line = (await self.cmd("AT+CGPSINFO") or [""])[0]
                f = line.split(":", 1)[-1].split(",")
                if len(f) >= 4 and f[0].strip():
                    lat = int(float(f[0]) / 100) + (float(f[0]) % 100) / 60
                    lon = int(float(f[2]) / 100) + (float(f[2]) % 100) / 60
                    return (-lat if f[1] == "S" else lat, -lon if f[3] == "W" else lon)
                await asyncio.sleep(2)
        except (ModemError, ValueError):
            pass
        finally:
            try:
                await self.cmd("AT+CGPS=0")
            except ModemError:
                pass
        return None


class SimModem(TelephonyBackend):
    """Stand-in modem for the PC and tests. Events come from inject_*()."""
    name = "sim7600"
    supports_sms = True

    def __init__(self, events: asyncio.Queue, echo: bool = True):
        self.events, self.echo = events, echo
        self.log: list[str] = []
        self.store: dict[int, str] = {}
        self.sent: list[tuple[str, str]] = []
        self._next = 0
        self.fail_alive = False
        self.csq = 22                # simulated reception (0/99 = no network)
        self.radio = True

    def _say(self, msg: str) -> None:
        self.log.append(msg)
        if self.echo:
            print(f"  [MODEM] {msg}", flush=True)

    async def start(self) -> None:
        self._say("bereit")

    # phone -> network
    async def dial(self, number):
        emergency = number in ("112", "110")       # emergency calls work even without our own network
        if not self.radio or (self.csq in (0, 99) and not emergency):
            raise ModemError("kein Mobilfunknetz (Simulation)")
        self._say(f"ATD{number};")
    async def answer(self): self._say("ATA")
    async def hangup(self): self._say("AT+CHUP")
    async def dtmf(self, d): self._say(f"AT+VTS={d}")
    async def call_volume(self, level): self._say(f"AT+CLVL={level}")
    async def signal(self): return self.csq if self.radio else None

    async def set_radio(self, on: bool) -> None:
        self.radio = on
        self._say(f"AT+CFUN={1 if on else 4}")
    async def alive(self): return not self.fail_alive
    async def gps_position(self, timeout=30): return (49.9497, 8.5664)
    async def stored_indices(self): return sorted(self.store)
    async def delete_sms(self, i): self.store.pop(i, None)

    async def read_sms(self, i):
        return pdu.decode_deliver(self.store[i]) if i in self.store else None

    async def send_sms(self, number, text):
        self.sent.append((number, text))
        self._say(f"SMS an {number}: {text}")

    # network -> phone (simulation)
    def inject(self, kind: str, data: str = "") -> None:
        self.events.put_nowait(ModemEvent(kind, data))

    def inject_call(self, number: str) -> None:
        self.inject("ring")
        self.inject("clip", number)

    def inject_sms(self, sender: str, text: str) -> None:
        for p in pdu.build_deliver(sender, text, ref=(self._next % 255) + 1):
            self._next += 1
            self.store[self._next] = p
            self.inject("sms", str(self._next))
