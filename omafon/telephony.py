"""Telephony interface: everything Phone needs from the network.

Phone only talks to a TelephonyBackend. Which backend runs is set in
config.yaml under ``backend``:

  sip      landline via the Fritz!Box as an IP phone (baresip, omafon/sip.py)
  hybrid   Fritz!Box at home + mobile network on the go (omafon/hybrid.py); the
           mobile part is omafon/modem.py (SIM7600, AT commands). A pure
           mobile phone is no longer a variant of its own.

Events to Phone (ModemEvent.kind):
  ring        incoming call is ringing (repeated while it rings)
  clip        caller's number (data = number, "" = withheld)
  call_begin  call is connected
  call_end, no_carrier, busy, no_answer, missed   call/attempt ended
  sms         new message available (data = index for read_sms)
  link_lost   connection to the network/Fritz!Box lost (only backends with link)
  link_ok     connection back
              For both, data may name a key from phone.P; Phone then says
              that text (e.g. "mode_home", "no_network").
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class ModemEvent:
    kind: str          # see module docs
    data: str = ""


class ModemError(Exception):
    pass


# Neutral names for new code; the old ones stay valid for existing imports.
TelephonyEvent = ModemEvent
TelephonyError = ModemError


class TelephonyBackend:
    """Base class. Required: start, dial, answer, hangup, dtmf, signal, alive.

    Optional capabilities have safe defaults here so Phone needs no special
    cases:
      - SMS/messages: stored_indices() empty, send_sms() raises ModemError
      - location: gps_position() returns None
      - connection: online is always True, status_words() None (= Phone uses CSQ)
    """

    name = "basis"
    supports_sms = False         # can text messages be sent?
    has_link = False             # reports link_lost/link_ok?
    offline_key = "link_lost"    # P key of the announcement when offline (Phone)

    # ---------------------------------------------------------------- required
    async def start(self) -> None:
        raise NotImplementedError

    async def dial(self, number: str) -> None:
        raise NotImplementedError

    async def answer(self) -> None:
        raise NotImplementedError

    async def hangup(self) -> None:
        raise NotImplementedError

    async def dtmf(self, digit: str) -> None:
        raise NotImplementedError

    async def signal(self) -> int | None:
        """Reception quality 0..31 (like AT+CSQ), None = no network."""
        raise NotImplementedError

    async def alive(self) -> bool:
        raise NotImplementedError

    # ---------------------------------------------------------------- optional
    @property
    def online(self) -> bool:
        return True

    def status_words(self) -> str | None:
        """Own announcement for the info key instead of "Empfang gut" (None = default)."""
        return None

    async def call_volume(self, level: int) -> None:
        return None

    def can_send_to(self, number: str) -> bool:
        """Can a text message be sent to this number?"""
        return self.supports_sms

    async def send_sms(self, number: str, text: str) -> None:
        raise ModemError("Nachrichten senden wird nicht unterstützt")

    async def stored_indices(self) -> list[int]:
        return []

    async def read_sms(self, index: int):
        return None

    async def delete_sms(self, index: int) -> None:
        return None

    async def gps_position(self, timeout: float = 30) -> tuple[float, float] | None:
        return None


BACKENDS = ("sip", "hybrid")


def create_backend(cfg, events: asyncio.Queue, loop: asyncio.AbstractEventLoop,
                   sim: bool = False):
    """Backend according to cfg.backend. sim=True: simulator without hardware/network.

    Returns: (backend, simulator_control). The control has inject_call,
    inject_sms and inject – for the simulator console and tests."""
    kind = getattr(cfg, "backend", "sip")
    if kind not in BACKENDS:
        raise ValueError(f"Unbekanntes backend '{kind}' – erlaubt: {', '.join(BACKENDS)}")
    if kind == "hybrid":
        from .hybrid import HybridBackend
        if sim:
            from .hybrid import HybridSimulator
            simulator = HybridSimulator(cfg)
            return simulator.backend(events), simulator
        from .modem import Modem
        from .sip import BaresipBackend
        return HybridBackend(
            cfg, events,
            home=lambda q: BaresipBackend(cfg, q),
            mobile=lambda q: Modem(cfg.serial_port, cfg.serial_baud, q, loop)), None
    from .sip import BaresipBackend
    if sim:
        from .sipsim import SipSimulator
        simulator = SipSimulator(cfg)
        return simulator.backend(events), simulator
    return BaresipBackend(cfg, events), None
