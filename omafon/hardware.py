"""Keys, battery, vibration, LED and modem power switch.

All keys are polled in a thread at 100 Hz. A key state only counts after the
debounce delay (80 ms) so that shaky fingers don't cause double triggers.
This produces KeyEvents:

  down  – key counts as pressed (digits are already announced here)
  short – released before long_press_s
  long  – held until long_press_s (no short afterwards)
  up    – released (always)
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass

log = logging.getLogger("omafon.hw")

# MCP23017: bit -> key (GPA0..7 = bits 0..7, GPB0..7 = bits 8..15)
MCP_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8",
            "9", "*", "0", "#", "CALL", "HANGUP", "MSG", "INFO"]

# directly on the Pi (BCM number, key, inverted)
PI_INPUTS = [
    (22, "SOS", False),
    (23, "SOS_COVER", True),     # microswitch: closed = cover shut -> invert
    (24, "VOL_UP", False),
    (25, "VOL_DOWN", False),
    (27, "CHARGER", False),      # bq24074 PGOOD: low = cradle/power supply
]
PIN_VIBRA, PIN_LED, PIN_MODEM_PWR = 12, 13, 6

DEBOUNCE_S = {"CHARGER": 0.5, "SOS_COVER": 0.15}
DEFAULT_DEBOUNCE_S = 0.08


@dataclass
class KeyEvent:
    key: str
    kind: str   # down, short, long, up
    held: float = 0.0   # for short/up: how long the key was pressed (s)


class KeyTracker:
    """Turns raw states (pressed yes/no) into KeyEvents."""

    def __init__(self, post, long_s: float, long_overrides: dict[str, float] | None = None):
        self.post = post
        self.long_s = long_s
        self.long_overrides = long_overrides or {}
        self.raw: dict[str, tuple[bool, float]] = {}
        self.state: dict[str, bool] = {}
        self.since: dict[str, float] = {}
        self.long_sent: dict[str, bool] = {}

    def update(self, key: str, pressed: bool, now: float) -> None:
        last_raw, t_raw = self.raw.get(key, (False, now))
        if pressed != last_raw:
            self.raw[key] = (pressed, now)
            t_raw = now
        stable = now - t_raw >= DEBOUNCE_S.get(key, DEFAULT_DEBOUNCE_S)
        cur = self.state.get(key, False)
        if stable and pressed != cur:
            self.state[key] = pressed
            if pressed:
                self.since[key] = now
                self.long_sent[key] = False
                self.post(KeyEvent(key, "down"))
            else:
                held = now - self.since.get(key, now)
                if not self.long_sent.get(key):
                    self.post(KeyEvent(key, "short", held))
                self.post(KeyEvent(key, "up", held))
        elif cur and not self.long_sent.get(key):
            if now - self.since[key] >= self.long_overrides.get(key, self.long_s):
                self.long_sent[key] = True
                self.post(KeyEvent(key, "long"))


class Hardware:
    def __init__(self, cfg, events: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        from gpiozero import Button, DigitalOutputDevice, PWMOutputDevice
        from smbus2 import SMBus
        self.bus = SMBus(1)
        self.loop, self.events = loop, events
        # MCP23017 (0x20): all pins input with pull-up
        for reg in (0x00, 0x01, 0x0C, 0x0D):
            self.bus.write_byte_data(0x20, reg, 0xFF)
        self.inputs = [(Button(pin, pull_up=True, bounce_time=None), key, inv)
                       for pin, key, inv in PI_INPUTS]
        self.vibra = PWMOutputDevice(PIN_VIBRA)
        self.led = DigitalOutputDevice(PIN_LED)
        self.modem_pwr = DigitalOutputDevice(PIN_MODEM_PWR)
        self.tracker = KeyTracker(self._post, cfg.long_press_s, {"SOS": cfg.sos_hold_s})
        threading.Thread(target=self._poll, daemon=True, name="keys").start()

    def _post(self, ev: KeyEvent) -> None:
        log.debug("Key %s %s", ev.key, ev.kind)
        self.loop.call_soon_threadsafe(self.events.put_nowait, ev)

    def _poll(self) -> None:
        errors = 0
        while True:
            now = time.monotonic()
            try:
                a = self.bus.read_byte_data(0x20, 0x12)
                b = self.bus.read_byte_data(0x20, 0x13)
                bits = a | (b << 8)
                for i, key in enumerate(MCP_KEYS):
                    self.tracker.update(key, not (bits >> i) & 1, now)
                errors = 0
            except OSError:
                errors += 1
                if errors == 50:
                    log.error("MCP23017 not responding – keypad failed")
            for btn, key, inv in self.inputs:  # SOS keeps working even without I²C
                self.tracker.update(key, btn.is_pressed != inv, now)
            time.sleep(0.01)

    # ------------------------------------------------------------ Outputs
    def vibrate(self, on: bool) -> None:
        self.vibra.value = 0.8 if on else 0

    def flash(self, on: bool) -> None:
        self.led.value = on

    def battery_percent(self) -> int | None:
        """MAX17048 (0x36), register 0x04 = SOC, high byte in percent."""
        try:
            hi, lo = self.bus.read_i2c_block_data(0x36, 0x04, 2)
            return max(0, min(100, round(hi + lo / 256)))
        except OSError:
            return None

    def on_charger(self) -> bool:
        return bool(self.tracker.state.get("CHARGER"))

    async def modem_power_cycle(self) -> None:
        """Waveshare HAT: a PWRKEY pulse toggles. Off, wait, on again."""
        for _ in range(2):
            self.modem_pwr.on()
            await asyncio.sleep(1.5)
            self.modem_pwr.off()
            await asyncio.sleep(8)


class SimHardware:
    def __init__(self, cfg, events: asyncio.Queue, echo: bool = True):
        self.events, self.echo = events, echo
        self.battery, self.charging = 80, False
        self.led = False
        self.log: list[str] = []
        self.cfg = cfg

    def _say(self, msg):
        self.log.append(msg)
        if self.echo:
            print(f"  [HW] {msg}", flush=True)

    def vibrate(self, on): self._say(f"Vibration {'an' if on else 'aus'}")
    def flash(self, on):
        if on != self.led:
            self.led = on
            self.log.append(f"LED {'an' if on else 'aus'}")   # don't log: blinks often
    def battery_percent(self): return self.battery
    def on_charger(self): return self.charging
    async def modem_power_cycle(self): self._say("Modem neu gestartet")

    def press(self, key: str, long: bool = False, held: float = 0.1) -> None:
        q = self.events.put_nowait
        q(KeyEvent(key, "down"))
        q(KeyEvent(key, "long" if long else "short", held))
        q(KeyEvent(key, "up", held))
