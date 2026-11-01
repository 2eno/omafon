"""Konfiguration aus config.yaml laden."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .numbers import normalize


@dataclass
class Contact:
    name: str                       # so wird der Name angesagt
    number: str
    speed_dial: int | None = None   # Taste 1–9 lang drücken
    emergency: int | None = None    # Reihenfolge in der Notrufkette (1 = zuerst)
    spoken: list[str] = field(default_factory=list)  # Wörter für die Spracherkennung
    admin: bool = False             # darf Status-SMS anfordern

    def words(self) -> list[str]:
        return [w.lower() for w in (self.spoken or [self.name])]


@dataclass
class Config:
    owner_name: str = "Oma"
    country_code: str = "49"
    contacts: list[Contact] = field(default_factory=list)
    emergency_ring_seconds: int = 30
    emergency_rounds: int = 2
    emergency_callback_minutes: int = 30
    quiet_hours: tuple[int, int] = (22, 7)
    default_route: str = "earpiece"          # "earpiece" oder "speaker"
    volume: int = 4                          # 1..5
    entry_timeout_s: int = 20
    long_press_s: float = 1.2
    sos_hold_s: float = 3.0
    sos_cancel_window_s: float = 5.0
    # Audio
    audio_device: str = "default"
    cache_dir: str = "/var/cache/omafon"
    piper_bin: str = "piper"
    piper_model: str = "/opt/omafon/voices/de_DE-thorsten-medium.onnx"
    speech_rate: float = 1.2                 # >1 = langsamer (Piper length_scale)
    # Spracherkennung
    vosk_model: str = "/opt/omafon/vosk-model-small-de-0.15"
    mic_device: str = "default"
    remote_stt_url: str | None = None        # z. B. http://10.8.0.1:9000/stt (Whisper)
    dictation_silence_s: float = 2.5
    dictation_max_s: float = 40.0
    # Hardware
    serial_port: str = "/dev/ttyAMA0"
    serial_baud: int = 115200
    data_dir: str = "/data/omafon"

    # ---- Abfragen
    def by_number(self, number: str) -> Contact | None:
        n = normalize(number, self.country_code)
        for c in self.contacts:
            if normalize(c.number, self.country_code) == n:
                return c
        return None

    def by_speed_dial(self, digit: int) -> Contact | None:
        return next((c for c in self.contacts if c.speed_dial == digit), None)

    def by_word(self, word: str) -> Contact | None:
        word = (word or "").strip().lower()
        for c in self.contacts:
            if word and any(w == word or w in word.split() for w in c.words()):
                return c
        return None

    def emergency_chain(self) -> list[Contact]:
        return sorted((c for c in self.contacts if c.emergency), key=lambda c: c.emergency)

    def name_for(self, number: str) -> str | None:
        c = self.by_number(number)
        return c.name if c else None


def load(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    contacts = [Contact(**c) for c in raw.pop("contacts", [])]
    if "quiet_hours" in raw:
        raw["quiet_hours"] = tuple(raw["quiet_hours"])
    known = Config.__dataclass_fields__
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"Unbekannte Einstellungen in {path}: {', '.join(sorted(unknown))}")
    return Config(contacts=contacts, **raw)
