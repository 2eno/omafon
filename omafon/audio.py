"""Speech output, tones and amplifier control.

Principle: a new announcement interrupts the old one immediately. Fixed
announcements (digits, menus, contact names) are generated once with
tools/prerender.py and kept as WAV in the cache – so the digit announcement
starts without noticeable delay.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import shutil
import struct
import wave
from pathlib import Path

log = logging.getLogger("omafon.audio")


class TPA2016:
    """TPA2016D2 (I²C 0x58): channel L = earpiece, channel R = speaker.

    Register layout per datasheet/Adafruit library – verify before use:
      0x01 bit7 SPK_EN_R, bit6 SPK_EN_L
      0x05 fixed gain (−28…+30 dB, 6-bit two's complement)
      0x06 bit7 limiter off, bit4:0 output limit
      0x07 bit7:4 maximum AGC gain, bit1:0 compression
    """
    ADDR = 0x58

    def __init__(self, bus: int = 1):
        from smbus2 import SMBus  # only available on the Pi
        self.bus = SMBus(bus)
        # compression 2:1, limiter on – keeps speech loud and clips peaks.
        self.bus.write_byte_data(self.ADDR, 0x07, (0x0C << 4) | 0x01)

    def route(self, earpiece: bool, speaker: bool) -> None:
        reg = self.bus.read_byte_data(self.ADDR, 0x01) & 0x3F
        reg |= (0x80 if speaker else 0) | (0x40 if earpiece else 0)
        self.bus.write_byte_data(self.ADDR, 0x01, reg)

    def gain(self, db: int) -> None:
        db = max(-28, min(30, db))
        self.bus.write_byte_data(self.ADDR, 0x05, db & 0x3F)

    def limit(self, level: int) -> None:
        """0 (quiet) … 31 (loud). Keep it low for the earpiece – hearing protection."""
        self.bus.write_byte_data(self.ADDR, 0x06, max(0, min(31, level)))


class Audio:
    # volume 1..5 -> gain in dB (speaker / earpiece)
    SPEAKER_DB = {1: 6, 2: 12, 3: 18, 4: 24, 5: 30}
    EARPIECE_DB = {1: -6, 2: 0, 3: 4, 4: 8, 5: 12}

    def __init__(self, cfg, amp: TPA2016 | None = None):
        self.cfg = cfg
        self.amp = amp
        self.cache = Path(cfg.cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self.route_mode = "speaker"
        self.volume = cfg.volume
        self._make_tones()

    # ------------------------------------------------------------ Tones
    def _tone(self, name: str, parts: list[tuple[float, float]], vol: float = 0.6) -> Path:
        """parts = [(frequency Hz or 0 for a pause, duration s), ...]"""
        path = self.cache / f"tone_{name}.wav"
        if path.exists():
            return path
        rate = 22050
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            for freq, dur in parts:
                n = int(rate * dur)
                for i in range(n):
                    env = min(1.0, i / 200, (n - i) / 200)  # soft edges, no clicks
                    v = math.sin(2 * math.pi * freq * i / rate) * vol * env if freq else 0
                    w.writeframes(struct.pack("<h", int(v * 32767)))
        return path

    def _make_tones(self) -> None:
        self.tones = {
            "beep": self._tone("beep", [(880, 0.15)]),
            "record": self._tone("record", [(660, 0.12), (0, 0.05), (990, 0.18)]),
            "gong": self._tone("gong", [(523, 0.25), (392, 0.4)], 0.4),
            "ring": self._tone("ring", [(440, 0.4), (480, 0.4), (0, 0.15), (440, 0.4), (480, 0.4)]),
            "sos": self._tone("sos", [(1200, 0.2), (0, 0.1)] * 3),
        }

    # ------------------------------------------------------------ Amplifier
    def route(self, mode: str) -> None:
        """'speaker', 'earpiece' or 'both'."""
        self.route_mode = mode
        self._apply()

    def set_volume(self, level: int) -> int:
        self.volume = max(1, min(5, level))
        self._apply()
        return self.volume

    def _apply(self) -> None:
        if not self.amp:
            return
        try:
            ear = self.route_mode in ("earpiece", "both")
            spk = self.route_mode in ("speaker", "both")
            self.amp.route(earpiece=ear, speaker=spk)
            table = self.EARPIECE_DB if ear and not spk else self.SPEAKER_DB
            self.amp.gain(table[self.volume])
            self.amp.limit(12 if ear and not spk else 31)
        except OSError as e:
            log.error("Amplifier not reachable: %s", e)

    # ------------------------------------------------------------ Speech
    def _cache_path(self, text: str) -> Path:
        key = f"{self.cfg.piper_model}|{self.cfg.speech_rate}|{text}"
        return self.cache / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".wav")

    async def synth(self, text: str) -> Path | None:
        path = self._cache_path(text)
        if path.exists():
            return path
        tmp = path.with_suffix(".tmp.wav")
        if shutil.which(self.cfg.piper_bin) and Path(self.cfg.piper_model).exists():
            cmd = [self.cfg.piper_bin, "--model", self.cfg.piper_model,
                   "--length_scale", str(self.cfg.speech_rate), "--output_file", str(tmp)]
        elif shutil.which("espeak-ng"):
            log.warning("Piper missing – falling back to espeak-ng")
            cmd = ["espeak-ng", "-v", "de", "-s", "135", "-w", str(tmp), text]
        else:
            log.error("No speech output installed")
            return None
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.communicate(text.encode("utf-8") if "piper" in cmd[0] else None)
        if proc.returncode == 0 and tmp.exists():
            tmp.rename(path)
            return path
        log.error("Speech synthesis failed: %r", text)
        return None

    async def stop(self) -> None:
        p = self._proc
        if p and p.returncode is None:
            p.terminate()
            try:
                await asyncio.wait_for(p.wait(), 1)
            except asyncio.TimeoutError:
                p.kill()

    async def play(self, path: Path | None, interrupt: bool = True) -> None:
        if path is None:
            return
        if interrupt:
            await self.stop()
        async with self._lock:
            self._proc = await asyncio.create_subprocess_exec(
                "aplay", "-q", "-D", self.cfg.audio_device, str(path),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await self._proc.wait()

    async def say(self, text: str, interrupt: bool = True) -> None:
        """Speaks text. Returns when finished or interrupted.

        A newer announcement always wins: if the next one was already requested
        during synthesis, this one is dropped here.
        """
        log.info("SAYS: %s", text)
        self._gen = getattr(self, "_gen", 0) + (1 if interrupt else 0)
        gen = self._gen
        if interrupt:
            await self.stop()
        path = await self.synth(text)
        if gen != self._gen:
            return
        await self.play(path, interrupt=False)

    async def tone(self, name: str, interrupt: bool = False) -> None:
        await self.play(self.tones[name], interrupt=interrupt)


class SimAudio(Audio):
    """For tests and the PC: writes announcements to a list instead of playing them."""

    def __init__(self, cfg, echo: bool = True):
        self.cfg, self.amp, self.echo = cfg, None, echo
        self.spoken: list[str] = []
        self.route_mode, self.volume = "speaker", cfg.volume
        self.tones = {}

    async def say(self, text: str, interrupt: bool = True) -> None:
        self.spoken.append(text)
        if self.echo:
            print(f"  [SAGT] {text}", flush=True)
        await asyncio.sleep(0)

    async def tone(self, name: str, interrupt: bool = False) -> None:
        self.spoken.append(f"<{name}>")
        if self.echo:
            print(f"  [TON]  {name}", flush=True)
        await asyncio.sleep(0)

    async def stop(self) -> None:
        pass

    async def play(self, path, interrupt: bool = True) -> None:
        self.spoken.append(f"<abspielen {Path(path).name}>")
        if self.echo:
            print(f"  [SPIELT] {path}", flush=True)
        await asyncio.sleep(0)

    def _apply(self) -> None:
        if self.echo:
            print(f"  [AUDIO] Weg={self.route_mode} Lautstärke={self.volume}", flush=True)
