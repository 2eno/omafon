"""Simulator for the landline backend: a rebuilt baresip (ctrl_tcp)
and a simulated Fritz!Box. The real BaresipBackend talks to FakeBaresip over
TCP – so the real protocol code is what gets tested.

Used by  python -m omafon.main --sim  (backend: sip)  and the tests.
"""
from __future__ import annotations

import asyncio
import io
import logging
import math
import struct
import wave

from .fritz import SimFritzBox
from .numbers import normalize
from .sip import BaresipBackend, ns_encode, ns_read
from .telephony import ModemError

log = logging.getLogger("omafon.sipsim")


class FakeBaresip:
    """Speaks baresip's ctrl_tcp protocol (subset)."""

    def __init__(self, aor: str = "sip:omafon@fritz.box"):
        self.aor = aor
        self.server: asyncio.base_events.Server | None = None
        self.port = 0
        self.writer: asyncio.StreamWriter | None = None
        self.commands: list[tuple[str, str]] = []
        self.reachable = True        # Fritz!Box reachable (registration works)
        self.call_id = 0
        self.fail: set[str] = set()  # commands that answer with ok=false

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.writer:
            self.writer.close()
        if self.server:
            self.server.close()

    async def drop_connection(self) -> None:
        """Like a baresip crash: the TCP connection drops."""
        if self.writer:
            self.writer.close()
            self.writer = None

    async def _client(self, reader, writer) -> None:
        self.writer = writer
        try:
            while True:
                msg = await ns_read(reader)
                cmd, params = msg.get("command", ""), msg.get("params", "")
                self.commands.append((cmd, params))
                ok = cmd not in self.fail
                if cmd == "dial" and not self.reachable:
                    ok = False
                await self._write({"response": True, "ok": ok, "data": "",
                                   "token": msg.get("token")})
                if ok:
                    await self._after(cmd, params)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    async def _write(self, obj: dict) -> None:
        if self.writer:
            self.writer.write(ns_encode(obj))
            await self.writer.drain()

    async def event(self, type_: str, param: str = "", **extra) -> None:
        await self._write({"event": True, "class": "call" if type_.startswith("CALL") else "register",
                           "type": type_, "param": param, "accountaor": self.aor,
                           "id": str(self.call_id), **extra})

    async def _after(self, cmd: str, params: str) -> None:
        if cmd == "uareg":
            await self.event("REGISTER_OK" if self.reachable else "REGISTER_FAIL")
        elif cmd == "dial":
            self.call_id += 1
            await self.event("CALL_OUTGOING", params, direction="outgoing", peeruri=params)
            await self.event("CALL_RINGING", params, direction="outgoing", peeruri=params)
        elif cmd == "accept":
            await self.event("CALL_ESTABLISHED", direction="incoming")
        elif cmd == "hangup":
            await self.event("CALL_CLOSED", "Connection reset by user")

    # network -> phone
    async def incoming(self, number: str) -> None:
        self.call_id += 1
        uri = f"sip:{number}@fritz.box" if number else "sip:anonymous@anonymous.invalid"
        # Deliberately misleading display name: must NEVER be announced.
        await self.event("CALL_INCOMING", uri, direction="incoming", peeruri=uri,
                         peerdisplayname="Ihre Bank")

    async def set_reachable(self, up: bool) -> None:
        self.reachable = up
        await self.event("REGISTER_OK" if up else "REGISTER_FAIL")


class LogNotifier:
    """Instead of Telegram/e-mail: remembers the messages (simulator, tests)."""

    def __init__(self, cfg, enabled: bool = True, echo: bool = True):
        self.cfg, self.enabled, self.echo = cfg, enabled, echo
        self.sent: list[tuple[str, str, str]] = []   # (name, number, text)

    def can_reach(self, number: str) -> bool:
        """Like Notifier: only contacts with a Telegram chat ID or e-mail."""
        c = self.cfg.by_number(number)
        return bool(self.enabled and c and (c.telegram_chat_id or c.email))

    async def send_to_number(self, number: str, text: str) -> None:
        c = self.cfg.by_number(number)
        if not self.can_reach(number):
            raise ModemError("kein Benachrichtigungsweg")
        self.sent.append((c.name, number, text))
        if self.echo:
            print(f"  [PUSH] an {c.name}: {text}", flush=True)


def tone_wav(seconds: float = 0.5, freq: float = 440) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / 8000)))
                               for i in range(int(8000 * seconds))))
    return buf.getvalue()


class SimBaresipBackend(BaresipBackend):
    def __init__(self, cfg, events, sim: "SipSimulator", **kw):
        super().__init__(cfg, events, fritz=sim.fritz, notifier=sim.notifier, spawn=False,
                         operstate_path="", **kw)
        self.sim = sim

    async def start(self) -> None:
        self.port = await self.sim.server.start()
        await super().start()


class SipSimulator:
    """Control for the simulator console and tests (same methods as SimModem)."""

    def __init__(self, cfg, echo: bool = True, phonebook: dict[str, str] | None = None):
        self.cfg = cfg
        self.server = FakeBaresip()
        if phonebook is None:                  # example: Fritz!Box phone book
            phonebook = {"+491711234567": "Peter", "06990009100": "Frau Schmidt von nebenan"}
        self.fritz = SimFritzBox(phonebook, cfg.country_code)
        self.notifier = LogNotifier(cfg, echo=echo)
        self.sip: SimBaresipBackend | None = None

    def backend(self, events: asyncio.Queue, **kw) -> SimBaresipBackend:
        self.sip = SimBaresipBackend(self.cfg, events, self, **kw)
        return self.sip

    def _bg(self, coro) -> None:
        asyncio.get_running_loop().create_task(coro)

    # same names as SimModem
    def inject_call(self, number: str) -> None:
        self._bg(self.server.incoming(number))

    def inject_sms(self, sender: str, text: str = "") -> None:
        """Puts a message on the Fritz!Box answering machine and queries right away."""
        name = self.fritz.book.get(normalize(sender, self.cfg.country_code), "")
        self.fritz.add_message(sender, tone_wav(), name)
        if self.sip:
            self._bg(self.sip.poll_tam())

    def inject(self, kind: str, data: str = "") -> None:
        if kind == "call_begin":
            self._bg(self.server.event("CALL_ESTABLISHED", direction="outgoing"))
        elif kind in ("call_end", "no_carrier"):
            self._bg(self.server.event("CALL_CLOSED", "Connection reset by peer"))
        elif kind == "busy":
            self._bg(self.server.event("CALL_CLOSED", "486 Busy Here"))
        elif kind == "no_answer":
            self._bg(self.server.event("CALL_CLOSED", "408 Request Timeout"))

    def link(self, up: bool) -> None:
        self._bg(self.server.set_reachable(up))
