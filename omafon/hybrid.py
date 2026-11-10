"""Backend "hybrid": one device, two paths – Fritz!Box at home, mobile on the go.

Both backends run at the same time (BaresipBackend = "home", modem = "mobile").
Each writes to its own queue; HybridBackend forwards the events to Phone,
filtered. Phone doesn't notice any of this.

Rules (rationale in docs/hybrid.md):
  * Ringing: whoever rings first owns the call. If the other path rings
    meanwhile, it is rejected there (no call waiting – too confusing).
  * Dialing: normally via `prefer` (default: home), otherwise via the other
    path. Emergency 110/112: at home via the landline (the line address is
    transmitted), otherwise mobile. If one path fails, the other one right away.
  * Messages: SMS (mobile) and answering machine (home) end up together in the
    inbox; the numbers are re-keyed.
  * Sending SMS: via mobile; without a network via Telegram/e-mail (notify).
  * Connection: "no network" only when BOTH paths are gone. Switching between
    home and on the go is only announced with announce_mode.
  * Power saving (home_modem: off): if the Fritz!Box is reliably reachable, the
    mobile part goes into airplane mode and wakes up again when leaving home.
    It is switched on immediately for emergency SMS and emergency calls.
"""
from __future__ import annotations

import asyncio
import logging
import time

from .numbers import signal_words
from .telephony import ModemError, ModemEvent, TelephonyBackend

log = logging.getLogger("omafon.hybrid")

HYBRID_DEFAULTS = {
    "prefer": "home",              # home | mobile – path for normal calls
    "emergency_prefer": "home",    # path for 110/112 when both work
    "home_modem": "on",            # on | off (power saving at home)
    "radio_off_after_s": 300,      # the Fritz!Box must be stable this long
    "radio_wake_s": 45,            # mobile needs this long after switching on
    "mobile_poll_s": 30,           # query reception (AT+CSQ)
    "no_network_grace_s": 10,      # only then announce "no network"
    "announce_mode": False,        # announce "Zu Hause …" / "Unterwegs …"
    "weak_wifi_dbm": -75,          # weaker Wi-Fi (garden, edge of the flat): prefer mobile
}
EMERGENCY = ("112", "110")
CALL_EVENTS = ("call_begin", "call_end", "no_carrier", "busy", "no_answer", "missed")


class HybridBackend(TelephonyBackend):
    name = "hybrid"
    has_link = True
    supports_sms = True
    offline_key = "no_network"

    def __init__(self, cfg, events: asyncio.Queue, home, mobile, clock=time.monotonic):
        """home/mobile: factories that build a backend from a queue."""
        self.cfg, self.events, self.clock = cfg, events, clock
        self.opt = {**HYBRID_DEFAULTS, **(getattr(cfg, "hybrid", None) or {})}
        hm = self.opt["home_modem"]              # YAML reads unquoted on/off as bool
        self.opt["home_modem"] = ("on" if hm else "off") if isinstance(hm, bool) else str(hm)
        self.q = {"home": asyncio.Queue(), "mobile": asyncio.Queue()}
        self.home = home(self.q["home"])
        self.mobile = mobile(self.q["mobile"])
        self.active: str | None = None           # who owns the current call
        self.mobile_csq: int | None = None
        self.mobile_started = False
        self.radio_on = True
        self.radio_on_since = clock()
        self.home_stable_since: float | None = None
        self.down_since: float | None = None
        self.announced_down = False
        self.mode: str | None = None
        self.msg_map: dict[int, tuple[str, int]] = {}
        self._next = 0
        self._tasks: list[asyncio.Task] = []
        self._last_poll = -1e9
        self._started = False

    # ------------------------------------------------------------ State
    def leg(self, name: str) -> TelephonyBackend:
        return self.home if name == "home" else self.mobile

    @property
    def mobile_ok(self) -> bool:
        return self.mobile_started and self.radio_on and self.mobile_csq not in (None, 0, 99)

    @property
    def online(self) -> bool:
        return self.home.online or self.mobile_ok

    def status_words(self) -> str:
        parts = []
        if self.home.online:
            parts.append(f"Zu Hause. {self.home.status_words()}")
        if not self.mobile_started:
            parts.append("Mobilfunkteil antwortet nicht.")
        elif not self.radio_on:
            parts.append("Mobilfunk ruht, Anrufe kommen über die Fritzbox.")
        else:
            parts.append(f"Mobilfunk: {signal_words(self.mobile_csq)}")
        return " ".join(parts)

    def _emit(self, kind: str, data: str = "") -> None:
        log.info("→ Phone %s %s", kind, data)
        self.events.put_nowait(ModemEvent(kind, data))

    # ------------------------------------------------------------ Start
    async def start(self) -> None:
        if self._started:                        # Phone restarted the modem
            await self._start_mobile()
            return
        self._started = True
        await self.home.start()                  # never raises
        await self._start_mobile()
        for name in ("home", "mobile"):
            self._tasks.append(asyncio.create_task(self._pump(name), name=f"hybrid-{name}"))
        self._tasks.append(asyncio.create_task(self._supervise(), name="hybrid-supervisor"))

    async def _start_mobile(self) -> None:
        try:
            await self.mobile.start()
            self.mobile_started = True
            await self.poll_mobile()
        except ModemError as e:                  # the landline works anyway
            self.mobile_started = False
            log.error("Mobile part does not start: %s", e)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        if hasattr(self.home, "stop"):
            await self.home.stop()

    # ------------------------------------------------------------ Events
    async def _pump(self, name: str) -> None:
        while True:
            ev = await self.q[name].get()
            try:
                await self.route(name, ev)
            except Exception:
                log.exception("Event %s from %s", ev, name)

    async def route(self, name: str, ev: ModemEvent) -> None:
        k = ev.kind
        if k in ("link_lost", "link_ok"):        # internal only: the overall state counts
            self.update_link()
            return
        if k == "sms":
            self._next += 1
            self.msg_map[self._next] = (name, int(ev.data))
            self._emit("sms", str(self._next))
            return
        if k == "ring":
            if self.active and self.active != name:
                log.info("Call via %s rejected – call via %s in progress", name, self.active)
                try:
                    await self.leg(name).hangup()
                except ModemError:
                    pass
                return
            self.active = name
            self._emit(k, ev.data)
        elif k == "clip":
            if self.active == name:
                self._emit(k, ev.data)
        elif k in CALL_EVENTS:
            if self.active != name:              # echo of a rejected call
                return
            if k != "call_begin":
                self.active = None
            self._emit(k, ev.data)
        else:
            self._emit(k, ev.data)

    # ------------------------------------------------------------ Monitoring
    async def _supervise(self) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await self.tick()
            except Exception:
                log.exception("Error in hybrid monitoring")

    async def tick(self) -> None:
        """Check once (public for tests)."""
        if self.clock() - self._last_poll >= float(self.opt["mobile_poll_s"]):
            await self.poll_mobile()
        await self._power_policy()
        self.update_link()

    async def poll_mobile(self) -> None:
        self._last_poll = self.clock()
        if not self.mobile_started or not self.radio_on:
            return
        try:
            self.mobile_csq = await self.mobile.signal()
        except ModemError:
            self.mobile_csq = None

    async def _power_policy(self) -> None:
        if self.opt["home_modem"] != "off" or not self.mobile_started:
            return
        now = self.clock()
        if self.home.online:
            self.home_stable_since = self.home_stable_since or now
            if (self.radio_on and self.active != "mobile"
                    and now - self.home_stable_since >= float(self.opt["radio_off_after_s"])):
                await self.set_radio(False)
        else:
            self.home_stable_since = None
            if not self.radio_on:                # left home / Wi-Fi gone
                await self.set_radio(True)

    async def set_radio(self, on: bool, wait: bool = False) -> None:
        log.info("Mobile %s", "an" if on else "aus (Sparmodus)")
        try:
            await self.mobile.set_radio(on)
        except ModemError as e:
            log.error("Switching radio: %s", e)
            return
        self.radio_on = on
        if on:
            self.radio_on_since = self.clock()
            self._last_poll = -1e9
            if wait:                             # wait for the network (emergency SMS)
                for _ in range(int(float(self.opt["radio_wake_s"]))):
                    await self.poll_mobile()
                    if self.mobile_ok:
                        break
                    await asyncio.sleep(1)
        else:
            self.mobile_csq = None

    def update_link(self) -> None:
        now = self.clock()
        mode = "home" if self.home.online else ("mobile" if self.mobile_ok else None)
        if self.online:
            self.down_since = None
            if self.announced_down:
                self.announced_down = False
                self._emit("link_ok", "network_ok")
            elif self.opt["announce_mode"] and self.mode and mode != self.mode:
                self._emit("link_ok", f"mode_{mode}")
            self.mode = mode
            return
        self.down_since = self.down_since or now
        waking = self.radio_on and now - self.radio_on_since < float(self.opt["radio_wake_s"])
        if (not self.announced_down and not waking
                and now - self.down_since >= float(self.opt["no_network_grace_s"])):
            self.announced_down = True
            self._emit("link_lost", "no_network")

    # ------------------------------------------------------------ Telephony
    def wifi_weak(self) -> bool:
        dbm = self.home._wifi_dbm() if hasattr(self.home, "_wifi_dbm") else None
        return dbm is not None and dbm < float(self.opt["weak_wifi_dbm"])

    def _order(self, number: str) -> list[str]:
        first = self.opt["emergency_prefer"] if number in EMERGENCY else self.opt["prefer"]
        if first == "home" and self.home.online and self.mobile_ok and self.wifi_weak():
            first = "mobile"                     # the call would drop at the edge of the Wi-Fi
        return [first, "mobile" if first == "home" else "home"]

    async def dial(self, number: str) -> None:
        number = number.strip()
        errors = []
        for name in self._order(number):
            if name == "home" and not self.home.online:
                errors.append("Fritz!Box nicht erreichbar")
                continue
            if name == "mobile":
                if not self.mobile_started:
                    errors.append("Mobilfunkteil antwortet nicht")
                    continue
                if not self.radio_on:            # power saving: wake up
                    await self.set_radio(True, wait=number not in EMERGENCY)
                if not self.mobile_ok and number not in EMERGENCY:
                    errors.append("kein Mobilfunknetz")
                    continue
            try:
                self.active = name
                await self.leg(name).dial(number)
                log.info("Dialing %s via %s", number, name)
                return
            except ModemError as e:
                self.active = None
                errors.append(f"{name}: {e}")
        raise ModemError("; ".join(errors) or "kein Weg zum Telefonieren")

    async def answer(self) -> None:
        if self.active:
            await self.leg(self.active).answer()

    async def hangup(self) -> None:
        name, self.active = self.active, None
        if name:
            await self.leg(name).hangup()

    async def dtmf(self, digit: str) -> None:
        if self.active:
            await self.leg(self.active).dtmf(digit)

    async def call_volume(self, level: int) -> None:
        if self.active == "mobile":
            await self.mobile.call_volume(level)

    async def signal(self) -> int | None:
        if self.home.online:
            return await self.home.signal()
        return self.mobile_csq if self.mobile_ok else None

    async def alive(self) -> bool:
        """Health of the mobile part – otherwise Phone restarts it.
        The landline path repairs itself."""
        if not self.mobile_started:
            return False
        return await self.mobile.alive()

    # ------------------------------------------------------------ Messages
    def can_send_to(self, number: str) -> bool:
        return self.mobile_started or self.home.can_send_to(number)

    async def send_sms(self, number: str, text: str) -> None:
        if self.mobile_started:
            if not self.radio_on:
                await self.set_radio(True, wait=True)
            if self.mobile_ok:
                try:
                    return await self.mobile.send_sms(number, text)
                except ModemError as e:
                    log.warning("SMS via mobile failed, trying push: %s", e)
        await self.home.send_sms(number, text)    # Telegram/e-mail (raises if there is no path)

    async def stored_indices(self) -> list[int]:
        out = []
        for name in ("mobile", "home"):
            try:
                for idx in await self.leg(name).stored_indices():
                    self._next += 1
                    self.msg_map[self._next] = (name, idx)
                    out.append(self._next)
            except ModemError as e:
                log.warning("Stored messages (%s): %s", name, e)
        return out

    async def read_sms(self, index: int):
        if index not in self.msg_map:
            return None
        name, idx = self.msg_map[index]
        return await self.leg(name).read_sms(idx)

    async def delete_sms(self, index: int) -> None:
        name, idx = self.msg_map.pop(index, (None, None))
        if name:
            await self.leg(name).delete_sms(idx)

    async def gps_position(self, timeout: float = 30):
        home = getattr(self.cfg, "home_position", None)
        if self.home.online and home:            # at home: address instead of GPS (poor indoors)
            return tuple(home)
        if self.mobile_started:
            if not self.radio_on:
                await self.set_radio(True)
            return await self.mobile.gps_position(timeout)
        return None


class HybridSimulator:
    """Control for the simulator and tests: SipSimulator + SimModem together."""

    def __init__(self, cfg, echo: bool = True):
        from .sipsim import SipSimulator
        self.cfg, self.echo = cfg, echo
        self.sip = SipSimulator(cfg, echo=echo)
        self.hybrid: HybridBackend | None = None
        self.modem = None

    def backend(self, events: asyncio.Queue, clock=time.monotonic, **kw) -> HybridBackend:
        from .modem import SimModem

        def make_mobile(q):
            self.modem = SimModem(q, echo=self.echo)
            return self.modem
        self.hybrid = HybridBackend(self.cfg, events,
                                    home=lambda q: self.sip.backend(q, clock=clock, **kw),
                                    mobile=make_mobile, clock=clock)
        return self.hybrid

    # console/tests
    def inject_call(self, number: str) -> None:
        """Call to the landline number when at home – otherwise to the mobile."""
        if self.hybrid and self.hybrid.home.online:
            self.sip.inject_call(number)
        else:
            self.modem.inject_call(number)

    def inject_mobile_call(self, number: str) -> None:
        self.modem.inject_call(number)

    def inject_sms(self, sender: str, text: str = "") -> None:
        self.modem.inject_sms(sender, text or "Hallo")

    def inject_voicemail(self, sender: str) -> None:
        self.sip.inject_sms(sender)

    def inject(self, kind: str, data: str = "") -> None:
        if self.hybrid and self.hybrid.active == "home":
            self.sip.inject(kind, data)
        else:
            self.modem.inject(kind, data)

    def link(self, up: bool) -> None:
        """Wi-Fi/Fritz!Box on or off (leaving/entering home)."""
        self.sip.link(up)

    def netz(self, up: bool) -> None:
        """Mobile network on or off (dead zone)."""
        self.modem.csq = 22 if up else 99
