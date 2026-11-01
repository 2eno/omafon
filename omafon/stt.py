"""Spracherkennung: Namen (mit fester Wortliste, sehr treffsicher) und freies Diktat.

Offline mit Vosk. Optional zusätzlich ein eigener Whisper-Server (remote_stt_url),
der eine WAV-Datei per HTTP-POST bekommt und JSON {"text": "..."} zurückgibt.
Fällt der Server aus, gilt das Vosk-Ergebnis.
"""
from __future__ import annotations

import array
import asyncio
import io
import json
import logging
import time
import urllib.request
import wave

log = logging.getLogger("omafon.stt")
RATE = 16000
CHUNK = 3200  # 0,1 s bei 16 kHz, 16 Bit


class Recognizer:
    def __init__(self, cfg):
        self.cfg = cfg
        self._model = None
        self.stop_flag = asyncio.Event()

    async def _load(self):
        if self._model is None:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            loop = asyncio.get_running_loop()
            self._model = await loop.run_in_executor(None, Model, self.cfg.vosk_model)
        return self._model

    def unload(self) -> None:
        """Gibt ~300 MB RAM frei, wenn länger nicht diktiert wird."""
        self._model = None

    async def _record(self, rec, max_s: float, silence_s: float, grammar: bool) -> tuple[str, bytes]:
        proc = await asyncio.create_subprocess_exec(
            "arecord", "-q", "-D", self.cfg.mic_device, "-f", "S16_LE", "-r", str(RATE),
            "-c", "1", "-t", "raw", stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        texts, pcm = [], bytearray()
        start = last_voice = time.monotonic()
        heard = False
        noise = None
        self.stop_flag.clear()
        try:
            while time.monotonic() - start < max_s and not self.stop_flag.is_set():
                data = await proc.stdout.read(CHUNK)
                if not data:
                    break
                pcm += data
                s = array.array("h", data)
                level = sum(abs(x) for x in s) / max(1, len(s))
                noise = level if noise is None else min(noise * 1.01 + 1, level)  # Grundrauschen
                if level > max(400, noise * 3):
                    last_voice, heard = time.monotonic(), True
                if rec.AcceptWaveform(data):
                    t = json.loads(rec.Result()).get("text", "")
                    if t:
                        texts.append(t)
                        if grammar:
                            break
                if heard and time.monotonic() - last_voice > silence_s:
                    break
        finally:
            proc.terminate()
            await proc.wait()
        final = json.loads(rec.FinalResult()).get("text", "")
        if final:
            texts.append(final)
        return " ".join(texts).strip(), bytes(pcm)

    async def listen_name(self, words: list[str], timeout: float = 6) -> str:
        from vosk import KaldiRecognizer
        model = await self._load()
        rec = KaldiRecognizer(model, RATE, json.dumps(sorted(set(words)) + ["[unk]"]))
        text, _ = await self._record(rec, timeout, 1.2, grammar=True)
        return text.replace("[unk]", "").strip()

    async def dictate(self) -> str:
        from vosk import KaldiRecognizer
        model = await self._load()
        rec = KaldiRecognizer(model, RATE)
        text, pcm = await self._record(rec, self.cfg.dictation_max_s,
                                       self.cfg.dictation_silence_s, grammar=False)
        if self.cfg.remote_stt_url and pcm:
            try:
                text = await asyncio.get_running_loop().run_in_executor(
                    None, self._remote, pcm) or text
            except Exception as e:
                log.warning("Whisper-Server nicht erreichbar, nutze Vosk: %s", e)
        return tidy(text)

    def _remote(self, pcm: bytes) -> str:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        req = urllib.request.Request(self.cfg.remote_stt_url, data=buf.getvalue(),
                                     headers={"Content-Type": "audio/wav"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()).get("text", "").strip()


def tidy(text: str) -> str:
    """Vosk liefert klein und ohne Satzzeichen: ersten Buchstaben groß, Punkt ans Ende."""
    text = " ".join(text.split())
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


class SimRecognizer:
    """Gibt vorher eingereihte Antworten zurück (Tests, PC-Simulation)."""

    def __init__(self):
        self.answers: asyncio.Queue[str] = asyncio.Queue()
        self.stop_flag = asyncio.Event()

    def unload(self): pass

    async def listen_name(self, words, timeout=6):
        try:
            return await asyncio.wait_for(self.answers.get(), timeout)
        except asyncio.TimeoutError:
            return ""

    async def dictate(self):
        try:
            return tidy(await asyncio.wait_for(self.answers.get(), 40))
        except asyncio.TimeoutError:
            return ""
