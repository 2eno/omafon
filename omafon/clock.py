"""Uhr des Telefons – ehrlich, auch ohne Netz.

Der Raspberry Pi hat keine gepufferte Uhr. Nach dem Einschalten ohne Netz steht
die Systemzeit auf dem zuletzt gespeicherten Stand (fake-hwclock), womöglich
Tage alt. Eine blinde Nutzerin würde einer falschen Uhrzeitansage glauben.
Darum:

  * known() sagt, ob die Zeit verlässlich ist: Kernel-Uhr synchron (NTP über
    WLAN) oder Netzzeit vom Mobilfunk (NITZ, siehe Modem.network_time()).
  * now() nimmt die Systemzeit, solange sie synchron ist, sonst die zuletzt
    übernommene Netzzeit plus die seither vergangene (monotone) Zeit.

Ob die Kernel-Uhr synchron ist, steht im Rückgabewert von adjtimex(2):
TIME_ERROR (5) heißt "nicht synchronisiert" – dieselbe Quelle, die
`timedatectl` als "System clock synchronized" anzeigt.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import datetime as dt
import logging
import time

log = logging.getLogger("omafon.clock")

TIME_ERROR = 5


def kernel_clock_synchronized() -> bool:
    """True, wenn der Kernel die Uhr als synchronisiert führt. Auf Systemen ohne
    adjtimex (macOS, Windows) oder wenn die Abfrage scheitert: True – dort gibt
    es keinen Grund, der Systemuhr zu misstrauen."""
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)
        adjtimex = libc.adjtimex
    except (OSError, AttributeError):
        return True
    buf = ctypes.create_string_buffer(512)        # struct timex, modes = 0: nur lesen
    state = adjtimex(buf)
    if state < 0:                                  # z. B. per seccomp verboten
        return True
    return state != TIME_ERROR


class Clock:
    def __init__(self, synchronized=kernel_clock_synchronized, wall=dt.datetime.now,
                 monotonic=time.monotonic, cache_s: float = 10.0):
        self._synchronized = synchronized
        self._wall = wall
        self._mono = monotonic
        self._cache_s = cache_s
        self._sync_cache: tuple[float, bool] | None = None
        self._ref: tuple[float, dt.datetime] | None = None   # (monoton, Netzzeit)

    def synchronized(self) -> bool:
        now = self._mono()
        if self._sync_cache is None or now - self._sync_cache[0] >= self._cache_s:
            self._sync_cache = (now, bool(self._synchronized()))
        return self._sync_cache[1]

    def known(self) -> bool:
        return self.synchronized() or self._ref is not None

    def now(self) -> dt.datetime:
        if self.synchronized() or self._ref is None:
            return self._wall()
        mono, t = self._ref
        return t + dt.timedelta(seconds=self._mono() - mono)

    def set_network_time(self, t: dt.datetime) -> None:
        """Netzzeit übernehmen (nur gebraucht, solange die Systemuhr nicht synchron ist)."""
        if self._ref is None:
            log.info("Uhrzeit vom Mobilfunknetz übernommen: %s", t.isoformat(timespec="minutes"))
        self._ref = (self._mono(), t)
