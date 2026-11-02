"""Telefonie-Schnittstelle: alles, was Phone vom Netz braucht.

Phone spricht nur mit einem TelephonyBackend. Welches Backend läuft, steht in
config.yaml unter ``backend``:

  sim7600  Mobilfunk über den Waveshare-HAT (AT-Befehle, omafon/modem.py)
  sip      Festnetz über die Fritz!Box als IP-Telefon (baresip, omafon/sip.py)

Ereignisse an Phone (ModemEvent.kind):
  ring        eingehender Anruf klingelt (wiederholt, solange es klingelt)
  clip        Rufnummer des Anrufers (data = Nummer, "" = unterdrückt)
  call_begin  Gespräch steht
  call_end, no_carrier, busy, no_answer, missed   Gespräch/Versuch beendet
  sms         neue Nachricht abrufbar (data = Index für read_sms)
  link_lost   Verbindung zum Netz/zur Fritz!Box weg (nur Backends mit link)
  link_ok     Verbindung wieder da
              Bei beiden darf data einen Schlüssel aus phone.P nennen, dann sagt
              Phone diesen Text (z. B. "mode_home", "no_network").
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class ModemEvent:
    kind: str          # siehe Moduldoku
    data: str = ""


class ModemError(Exception):
    pass


# Neutrale Namen für neuen Code; die alten bleiben für bestehende Importe gültig.
TelephonyEvent = ModemEvent
TelephonyError = ModemError


class TelephonyBackend:
    """Basisklasse. Pflicht: start, dial, answer, hangup, dtmf, signal, alive.

    Optionale Fähigkeiten haben hier sichere Standardwerte, damit Phone ohne
    Fallunterscheidung auskommt:
      - SMS/Nachrichten: stored_indices() leer, send_sms() wirft ModemError
      - Ortung: gps_position() liefert None
      - Verbindung: online ist immer True, status_words() None (= Phone nutzt CSQ)
    """

    name = "basis"
    supports_sms = False         # Textnachrichten senden möglich?
    has_link = False             # meldet link_lost/link_ok?
    offline_key = "link_lost"    # P-Schlüssel der Ansage, wenn offline (Phone)

    # ---------------------------------------------------------------- Pflicht
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
        """Empfangsqualität 0..31 (wie AT+CSQ), None = kein Netz."""
        raise NotImplementedError

    async def alive(self) -> bool:
        raise NotImplementedError

    # ---------------------------------------------------------------- optional
    @property
    def online(self) -> bool:
        return True

    def status_words(self) -> str | None:
        """Eigene Ansage für die Info-Taste statt "Empfang gut" (None = Standard)."""
        return None

    async def call_volume(self, level: int) -> None:
        return None

    def can_send_to(self, number: str) -> bool:
        """Kann eine Textnachricht an diese Nummer gehen?"""
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


BACKENDS = ("sim7600", "sip", "hybrid")


def create_backend(cfg, events: asyncio.Queue, loop: asyncio.AbstractEventLoop,
                   sim: bool = False):
    """Backend laut cfg.backend. sim=True: Simulator ohne Hardware/Netz.

    Rückgabe: (backend, simulator_steuerung). Die Steuerung hat inject_call,
    inject_sms und inject – für die Simulator-Konsole und Tests.
    """
    kind = getattr(cfg, "backend", "sim7600")
    if kind not in BACKENDS:
        raise ValueError(f"Unbekanntes backend '{kind}' – erlaubt: {', '.join(BACKENDS)}")
    if kind == "sim7600":
        from .modem import Modem, SimModem
        if sim:
            m = SimModem(events)
            return m, m
        return Modem(cfg.serial_port, cfg.serial_baud, events, loop), None
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
