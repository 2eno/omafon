"""Backend "sip": landline via the Fritz!Box as an IP phone (Wi-Fi).

Telephony is done by baresip (apt install baresip). Omafon starts it as a
child process and controls it through the ctrl_tcp module: JSON in netstrings,
commands dial/accept/hangup/sndcode, events REGISTER_OK, CALL_INCOMING,
CALL_ESTABLISHED, CALL_CLOSED … (names from baresip src/bevent.c).

In addition:
  * Query the Fritz!Box answering machine via TR-064 (omafon/fritz.py) –
    new messages appear to Phone like an SMS with an audio file.
  * Load the Fritz!Box phone book into cfg.phonebook (name announcement).
  * Monitor the connection: link_lost/link_ok to Phone, automatic recovery
    (restart baresip, re-register, reconnect Wi-Fi).
  * "SMS" (emergency notice, dictation) via Telegram/e-mail (omafon/notify.py).

Security note: names are announced ONLY from the Fritz!Box phone book and the
contacts, never from the caller's SIP display name – a caller can set that
freely ("Police", "Your bank").
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from . import pdu
from .telephony import ModemError, ModemEvent, TelephonyBackend

log = logging.getLogger("omafon.sip")

SIP_DEFAULTS = {
    "registrar": "fritz.box",
    "user": "",                  # user name of the IP phone in the Fritz!Box
    "password": "",
    "baresip_bin": "baresip",
    "ctrl_port": 4444,
    "regint": 300,               # seconds between re-registrations
    "link_grace_s": 10,          # the connection may be gone this long before it is announced
    "reregister_s": 60,          # then let baresip re-register
    "restart_s": 120,            # then restart baresip
    "wifi_reset_s": 180,         # then reconnect Wi-Fi (wifi_reset_cmd)
    "wifi_reset_cmd": "nmcli radio wifi off && sleep 2 && nmcli radio wifi on",
    "wifi_iface": "wlan0",
    "ring_repeat_s": 3,          # repeat "ring" to Phone while it rings
}
FRITZ_DEFAULTS = {
    "host": "fritz.box",
    "user": "",                  # Fritz!Box user for TR-064
    "password": "",
    "tam": 0,                    # answering machine number (0 = first)
    "phonebook_id": 0,
    "tam_poll_s": 60,
    "phonebook_refresh_s": 1800,
    "tam_after_fetch": "mark",   # mark = mark as listened, delete, keep
}


# ------------------------------------------------------------------ Helpers
def ns_encode(obj: dict) -> bytes:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return str(len(data)).encode() + b":" + data + b","


async def ns_read(reader: asyncio.StreamReader) -> dict:
    head = await reader.readuntil(b":")
    n = int(head[:-1])
    if n > 1_000_000:
        raise ValueError("Netstring zu lang")
    data = await reader.readexactly(n + 1)
    if data[-1:] != b",":
        raise ValueError("Netstring ohne Komma")
    return json.loads(data[:-1].decode("utf-8"))


_URI_USER = re.compile(r"^(?:sips?|tel):([^@;>]+)")


def peer_number(uri: str) -> str:
    """'sip:+491711234567@fritz.box' -> '+491711234567'; anonymous -> ''."""
    uri = (uri or "").strip().strip("<>")
    m = _URI_USER.match(uri)
    user = m.group(1) if m else ""
    user = user.split(";")[0]
    return user if re.fullmatch(r"[+*#0-9]+", user or "") else ""


def close_kind(reason: str) -> str:
    r = (reason or "").lower()
    if "486" in r or "busy" in r or "600" in r:
        return "busy"
    if "480" in r or "408" in r or "timeout" in r or "unavailable" in r:
        return "no_answer"
    return "call_end"


def dbm_to_csq(dbm: float) -> int:
    """Map the Wi-Fi level (dBm) to the 0..31 scale of AT+CSQ."""
    return max(0, min(31, round((dbm + 90) * 31 / 40)))


@dataclass
class VoiceMessage(pdu.Deliver):
    """Answering machine message – an 'SMS' with an audio file for Phone."""
    audio: str = ""


def baresip_files(cfg, sip: dict) -> dict[str, str]:
    """Contents of config and accounts for baresip (password only in accounts)."""
    dev = cfg.audio_device
    config = f"""# von Omafon erzeugt – nicht von Hand ändern
poll_method\t\tepoll
sip_trans_def\t\tudp
call_accept\t\tno
audio_player\t\talsa,{dev}
audio_source\t\talsa,{cfg.mic_device}
audio_alert\t\talsa,{dev}
audio_telev_pt\t\t101
ringback_disabled\tno
module_path\t\t/usr/lib/baresip/modules
module\t\t\tg722.so
module\t\t\tg711.so
module\t\t\tauconv.so
module\t\t\tauresamp.so
module\t\t\talsa.so
module_app\t\taccount.so
module_app\t\tmenu.so
module_app\t\tnetroam.so
module_app\t\tctrl_tcp.so
ctrl_tcp_listen\t\t127.0.0.1:{int(sip['ctrl_port'])}
"""
    accounts = (f"<sip:{sip['user']}@{sip['registrar']}>;auth_pass={sip['password']};"
                f"regint={int(sip['regint'])};answermode=manual;"
                f"audio_codecs=G722,PCMA/8000,PCMU/8000\n")
    return {"config": config, "accounts": accounts}


# ------------------------------------------------------------------ Backend
class BaresipBackend(TelephonyBackend):
    name = "sip"
    has_link = True

    def __init__(self, cfg, events: asyncio.Queue, fritz=None, notifier=None,
                 spawn: bool = True, host: str = "127.0.0.1", port: int | None = None,
                 wireless_path: str = "/proc/net/wireless",
                 operstate_path: str | None = None, clock=time.monotonic):
        self.cfg, self.events = cfg, events
        self.sip = {**SIP_DEFAULTS, **(getattr(cfg, "sip", None) or {})}
        self.fritz_opts = {**FRITZ_DEFAULTS, **(getattr(cfg, "fritz", None) or {})}
        self.spawn, self.host = spawn, host
        self.port = int(port or self.sip["ctrl_port"])
        self.wireless_path = wireless_path
        self.operstate_path = operstate_path if operstate_path is not None else \
            f"/sys/class/net/{self.sip['wifi_iface']}/operstate"
        self.wifi_up = True
        self.clock = clock
        if fritz is None and self.fritz_opts["user"]:
            from .fritz import FritzBox
            o = self.fritz_opts
            fritz = FritzBox(o["host"], o["user"], o["password"], cfg.country_code,
                             int(o["tam"]), int(o["phonebook_id"]))
        self.fritz = fritz
        if notifier is None:
            from .notify import Notifier
            notifier = Notifier(cfg)
        self.notifier = notifier
        self.proc: asyncio.subprocess.Process | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.registered = False
        self.link_announced_down = False
        self.offline_since: float | None = self.clock()
        self._escalated: set[str] = set()
        self._tokens = itertools.count(1)
        self._pending: dict[str, asyncio.Future] = {}
        self._tasks: list[asyncio.Task] = []
        self._ring_task: asyncio.Task | None = None
        self.in_call = False
        self.store: dict[int, VoiceMessage] = {}
        self._next_idx = 0
        self._seen: set[tuple] = set()
        self._tam_lock = asyncio.Lock()   # never two queries at once (otherwise duplicates)
        self.log: list[str] = []      # commands sent (for tests/simulator)

    # ------------------------------------------------------------ Properties
    @property
    def supports_sms(self) -> bool:  # type: ignore[override]
        return self.notifier.enabled

    @property
    def online(self) -> bool:
        return self.connected and self.registered and self.wifi_up

    def _read_wifi_up(self) -> bool:
        """Wi-Fi interface connected? If the file is missing (PC, tests): yes."""
        if not self.operstate_path:
            return True
        try:
            return Path(self.operstate_path).read_text().strip() != "down"
        except OSError:
            return True

    def status_words(self) -> str:
        if not self.online:
            return "Keine Verbindung zur Fritzbox."
        dbm = self._wifi_dbm()
        if dbm is None or dbm >= -67:
            return "Verbindung zur Fritzbox gut."
        if dbm >= -75:
            return "Verbindung zur Fritzbox mittel."
        return "Verbindung zur Fritzbox schwach."

    def _emit(self, kind: str, data: str = "") -> None:
        log.info("Event %s %s", kind, data)
        self.events.put_nowait(ModemEvent(kind, data))

    # ------------------------------------------------------------ Start/stop
    async def start(self) -> None:
        """Starts baresip and the monitoring. Never raises: if the connection is
        missing, the monitoring reports link_lost and restores it itself."""
        if self.spawn:
            await self._spawn()
        await self._connect()
        self._tasks.append(asyncio.create_task(self._supervise(), name="sip-supervisor"))
        if self.fritz is not None:
            self._tasks.append(asyncio.create_task(self._fritz_loop(), name="fritz"))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        if self._ring_task:
            self._ring_task.cancel()
        if self.writer:
            self.writer.close()
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()

    async def _spawn(self) -> None:
        if self.proc and self.proc.returncode is None:
            return
        if not shutil.which(self.sip["baresip_bin"]):
            log.error("baresip missing (sudo apt install baresip)")
            return
        if not self.sip["user"] or not self.sip["password"]:
            log.error("sip.user/sip.password missing in config.yaml")
        d = Path(self.cfg.data_dir) / "baresip"
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
        for name, text in baresip_files(self.cfg, self.sip).items():
            p = d / name
            p.write_text(text, encoding="utf-8")
            os.chmod(p, 0o600)
        self.proc = await asyncio.create_subprocess_exec(
            self.sip["baresip_bin"], "-f", str(d), stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        log.info("baresip started (pid %s)", self.proc.pid)

    async def _connect(self, attempts: int = 10) -> bool:
        for _ in range(attempts):
            try:
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                self.connected = True
                self._tasks.append(asyncio.create_task(self._read_loop(), name="sip-reader"))
                log.info("ctrl_tcp connected")
                # registration state is unknown -> have it re-register
                try:
                    await self._send("uareg", str(int(self.sip["regint"])))
                except ModemError:
                    pass
                return True
            except OSError:
                await asyncio.sleep(0.5)
        self.connected = False
        self._link_changed()
        return False

    # ------------------------------------------------------------ Protocol
    async def _send(self, command: str, params: str = "", timeout: float = 5) -> str:
        if not self.connected or not self.writer:
            raise ModemError("Keine Verbindung zu baresip")
        token = str(next(self._tokens))
        fut = asyncio.get_running_loop().create_future()
        self._pending[token] = fut
        self.log.append(f"{command} {params}".strip())
        try:
            self.writer.write(ns_encode({"command": command, "params": params, "token": token}))
            await self.writer.drain()
            resp = await asyncio.wait_for(fut, timeout)
        except (OSError, asyncio.TimeoutError) as e:
            raise ModemError(f"baresip antwortet nicht auf {command}: {e!r}") from e
        finally:
            self._pending.pop(token, None)
        if not resp.get("ok"):
            raise ModemError(f"{command}: {resp.get('data', '')}".strip())
        return resp.get("data", "")

    async def _read_loop(self) -> None:
        try:
            while True:
                msg = await ns_read(self.reader)
                if msg.get("response"):
                    fut = self._pending.get(str(msg.get("token")))
                    if fut and not fut.done():
                        fut.set_result(msg)
                elif msg.get("event"):
                    await self._on_event(msg)
        except (asyncio.IncompleteReadError, ConnectionError, ValueError) as e:
            log.warning("ctrl_tcp disconnected: %r", e)
        finally:
            self.connected = False
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("getrennt"))
            if self.in_call:                     # the call is gone along with baresip
                self._call_over("call_end")
            self._link_changed()

    async def _on_event(self, ev: dict) -> None:
        t = ev.get("type", "")
        if t == "REGISTER_OK":
            self.registered = True
            self._link_changed()
        elif t in ("REGISTER_FAIL", "UNREGISTERING"):
            self.registered = False
            self._link_changed()
        elif t == "CALL_INCOMING":
            if self.in_call:                      # call waiting: reject the second call
                return
            self.in_call = True
            # Omafon rings itself. Don't wait here: this loop reads the answer.
            self._fire("stopringing")
            self._emit("ring")
            self._emit("clip", peer_number(ev.get("peeruri", "")))
            self._ring_task = asyncio.create_task(self._ring_repeat())
        elif t == "CALL_ESTABLISHED":
            self._stop_ring()
            self._emit("call_begin")
        elif t == "CALL_CLOSED":
            self._call_over(close_kind(ev.get("param", "")))

    def _fire(self, command: str, params: str = "") -> None:
        """Command without waiting for the answer (from within the read loop)."""
        async def run():
            try:
                await self._send(command, params)
            except ModemError as e:
                log.warning("%s: %s", command, e)
        t = asyncio.create_task(run())
        self._tasks.append(t)
        t.add_done_callback(lambda t: self._tasks.remove(t) if t in self._tasks else None)

    def _call_over(self, kind: str) -> None:
        self._stop_ring()
        self.in_call = False
        self._emit(kind)

    async def _ring_repeat(self) -> None:
        while True:
            await asyncio.sleep(float(self.sip["ring_repeat_s"]))
            self._emit("ring")

    def _stop_ring(self) -> None:
        if self._ring_task and not self._ring_task.done():
            self._ring_task.cancel()
        self._ring_task = None

    # ------------------------------------------------------------ Connection
    def _link_changed(self) -> None:
        if self.online:
            self.offline_since = None
            self._escalated.clear()
            if self.link_announced_down:
                self.link_announced_down = False
                self._emit("link_ok")
        elif self.offline_since is None:
            self.offline_since = self.clock()

    async def _supervise(self) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await self.check_link()
            except Exception:
                log.exception("Error in connection monitoring")

    async def check_link(self) -> None:
        """Check once and escalate if needed (public for tests)."""
        up = self._read_wifi_up()
        if up != self.wifi_up:
            log.warning("Wi-Fi %s", "wieder da" if up else "weg")
            self.wifi_up = up
            if self.in_call and not up:           # the call is lost without Wi-Fi
                try:
                    await self._send("hangup", timeout=2)
                except ModemError:
                    pass
                self._call_over("call_end")
        self._link_changed()
        if self.online:
            return
        if self.offline_since is None:
            self.offline_since = self.clock()
        down = self.clock() - self.offline_since
        if down >= float(self.sip["link_grace_s"]) and not self.link_announced_down:
            self.link_announced_down = True
            self._emit("link_lost")
        if self.spawn and self.proc is not None and self.proc.returncode is not None:
            log.warning("baresip exited (%s) – restarting", self.proc.returncode)
            await self._spawn()
        if not self.connected:
            await self._connect(attempts=1)
            return
        steps = (("reregister", "reregister_s"), ("restart", "restart_s"),
                 ("wifi", "wifi_reset_s"))
        for step, key in steps:
            if down >= float(self.sip[key]) and step not in self._escalated:
                self._escalated.add(step)
                await self._escalate(step)
                break

    async def _escalate(self, step: str) -> None:
        log.warning("Fritz!Box unreachable – step %s", step)
        if step == "reregister":
            try:
                await self._send("uareg", str(int(self.sip["regint"])))
            except ModemError:
                pass
        elif step == "restart" and self.spawn and self.proc:
            self.proc.terminate()                 # monitoring restarts
        elif step == "wifi" and self.sip["wifi_reset_cmd"]:
            p = await asyncio.create_subprocess_shell(
                self.sip["wifi_reset_cmd"], stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await p.wait()
        if step == "wifi":                        # then escalate from the start
            self._escalated.clear()
            self.offline_since = self.clock() - float(self.sip["link_grace_s"])

    def _wifi_dbm(self) -> float | None:
        try:
            for line in Path(self.wireless_path).read_text().splitlines()[2:]:
                parts = line.split()
                if parts and parts[0].rstrip(":") == self.sip["wifi_iface"]:
                    return float(parts[3].rstrip("."))
        except (OSError, ValueError, IndexError):
            pass
        return None

    # ------------------------------------------------------------ Telephony
    def _uri(self, number: str) -> str:
        number = number.strip().replace(" ", "")
        return f"sip:{number}@{self.sip['registrar']}"

    async def dial(self, number: str) -> None:
        if not self.online:
            raise ModemError("Keine Verbindung zur Fritz!Box")
        self.in_call = True
        try:
            await self._send("dial", self._uri(number), timeout=10)
        except ModemError:
            self.in_call = False
            raise

    async def answer(self) -> None:
        self._stop_ring()
        await self._send("accept")

    async def hangup(self) -> None:
        self._stop_ring()
        self.in_call = False
        await self._send("hangup")

    async def dtmf(self, digit: str) -> None:
        await self._send("sndcode", digit)

    async def signal(self) -> int | None:
        if not self.online:
            return None
        dbm = self._wifi_dbm()
        return 31 if dbm is None else dbm_to_csq(dbm)

    async def alive(self) -> bool:
        """True while our own monitoring runs – it restores the connection
        itself (Phone should not restart a mobile module)."""
        sup = next((t for t in self._tasks if t.get_name() == "sip-supervisor"), None)
        return sup is not None and not sup.done()

    # ------------------------------------------------------------ Messages
    def can_send_to(self, number: str) -> bool:
        return self.notifier.can_reach(number)

    async def send_sms(self, number: str, text: str) -> None:
        await self.notifier.send_to_number(number, text)

    async def stored_indices(self) -> list[int]:
        return sorted(self.store)

    async def read_sms(self, index: int):
        return self.store.get(index)

    async def delete_sms(self, index: int) -> None:
        self.store.pop(index, None)

    async def gps_position(self, timeout: float = 30):
        pos = getattr(self.cfg, "home_position", None)
        return tuple(pos) if pos else None

    # ------------------------------------------------------------ Fritz!Box
    async def _fritz_loop(self) -> None:
        last_book = -1e9
        while True:
            try:
                if self.clock() - last_book >= float(self.fritz_opts["phonebook_refresh_s"]):
                    await self.refresh_phonebook()
                    last_book = self.clock()
                await self.poll_tam()
            except Exception as e:      # Fritz!Box gone, wrong password …
                log.warning("Fritz!Box query failed: %r", e)
            await asyncio.sleep(float(self.fritz_opts["tam_poll_s"]))

    async def refresh_phonebook(self) -> int:
        book = await asyncio.get_running_loop().run_in_executor(None, self.fritz.phonebook)
        self.cfg.phonebook = book
        log.info("Phone book: %d numbers", len(book))
        return len(book)

    async def poll_tam(self) -> int:
        """Fetch new answering machine messages; one 'sms' event per message. Returns: count."""
        async with self._tam_lock:
            return await self._poll_tam()

    async def _poll_tam(self) -> int:
        loop = asyncio.get_running_loop()
        msgs, list_url = await loop.run_in_executor(None, self.fritz.tam_messages)
        found = 0
        for m in reversed(msgs):                       # oldest first
            key = (m.tam, m.index, m.time)
            if not m.new or key in self._seen:
                continue
            raw = await loop.run_in_executor(None, self.fritz.download, list_url, m)
            audio = await self._store_audio(raw, f"ab_{m.tam}_{m.index}_{int(time.time())}")
            self._next_idx += 1                       # Phone sets the announcement text (P dict)
            self.store[self._next_idx] = VoiceMessage(
                sender=m.number, text="", timestamp=m.time, audio=audio)
            self._seen.add(key)
            after = self.fritz_opts["tam_after_fetch"]
            if after in ("mark", "delete"):
                await loop.run_in_executor(None, getattr(self.fritz,
                                           "mark_read" if after == "mark" else "delete"), m)
            self._emit("sms", str(self._next_idx))
            found += 1
        return found

    async def _store_audio(self, raw: bytes, stem: str) -> str:
        d = Path(self.cfg.data_dir) / "voicemail"
        d.mkdir(parents=True, exist_ok=True)
        wav = d / f"{stem}.wav"
        if raw[:4] == b"RIFF":
            wav.write_bytes(raw)
            return str(wav)
        # unknown format: ffmpeg usually detects it itself (see open questions)
        src = d / f"{stem}.raw"
        src.write_bytes(raw)
        if shutil.which("ffmpeg"):
            p = await asyncio.create_subprocess_exec(
                "ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
                str(wav), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            if await p.wait() == 0 and wav.exists():
                src.unlink(missing_ok=True)
                return str(wav)
        log.error("Answering machine recording %s not playable (unknown format)", src.name)
        return ""

