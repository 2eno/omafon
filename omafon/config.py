"""Load the configuration from config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .numbers import normalize


@dataclass
class Contact:
    name: str                       # this is how the name is announced
    number: str
    speed_dial: int | None = None   # long press on key 1–9
    emergency: int | None = None    # position in the emergency chain (1 = first)
    spoken: list[str] = field(default_factory=list)  # words for speech recognition
    admin: bool = False             # may request status SMS
    telegram_chat_id: int | str | None = None   # landline: emergency/messages via Telegram
    email: str | None = None                    # landline: emergency/messages via e-mail

    def words(self) -> list[str]:
        return [w.lower() for w in (self.spoken or [self.name])]


@dataclass
class Config:
    owner_name: str = "Oma"
    backend: str = "sip"                     # "sip" (Fritz!Box) or "hybrid" (Fritz!Box + mobile)
    country_code: str = "49"
    contacts: list[Contact] = field(default_factory=list)
    emergency_ring_seconds: int = 30
    emergency_rounds: int = 2
    emergency_callback_minutes: int = 30
    quiet_hours: tuple[int, int] = (22, 7)
    news_signal_minutes: int = 10            # gong reminder for unread SMS (0 = only once)
    news_led: bool = True                    # LED blinks for unread SMS
    default_route: str = "earpiece"          # "earpiece" or "speaker"
    volume: int = 4                          # 1..5
    entry_timeout_s: int = 20
    long_press_s: float = 1.2
    hangup_hold_s: float = 0.5               # during a call: hang up only after holding this long (0 = immediately)
    sos_hold_s: float = 3.0
    sos_cancel_window_s: float = 5.0
    # Audio
    audio_device: str = "default"
    cache_dir: str = "/var/cache/omafon"
    piper_bin: str = "piper"
    piper_model: str = "/opt/omafon/voices/de_DE-thorsten-medium.onnx"
    speech_rate: float = 1.2                 # >1 = slower (Piper length_scale)
    # speech recognition
    vosk_model: str = "/opt/omafon/vosk-model-small-de-0.15"
    mic_device: str = "default"
    remote_stt_url: str | None = None        # e.g. http://10.8.0.1:9000/stt (Whisper)
    dictation_silence_s: float = 2.5
    dictation_max_s: float = 40.0
    # Hardware
    serial_port: str = "/dev/ttyAMA0"
    serial_baud: int = 115200
    data_dir: str = "/data/omafon"
    # landline (backend: sip) – keys see omafon/sip.py, fritz.py, notify.py
    sip: dict = field(default_factory=dict)
    fritz: dict = field(default_factory=dict)
    notify: dict = field(default_factory=dict)
    hybrid: dict = field(default_factory=dict)      # keys see omafon/hybrid.py
    phonebook: dict = field(default_factory=dict)   # number -> name (loaded from the Fritz!Box)
    home_position: list[float] | None = None        # [latitude, longitude] for the emergency notice, optional
    link_reminder_minutes: int = 10                  # connection lost: repeat the announcement
    # cradle
    answer_on_lift: bool = False             # lifting from the cradle answers the call
    dock_in_call: str = "ignore"             # putting down during a call: ignore | hangup | handsfree
    dock_speaker: bool = False               # the cradle has a speaker: hands-free there

    # ---- Queries
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
        """Name from the contacts, otherwise from the Fritz!Box phone book."""
        c = self.by_number(number)
        if c:
            return c.name
        if self.phonebook and number:
            return self.phonebook.get(normalize(number, self.country_code))
        return None


def load(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    contacts = [Contact(**c) for c in raw.pop("contacts", [])]
    if "quiet_hours" in raw:
        raw["quiet_hours"] = tuple(raw["quiet_hours"])
    cc = str(raw.get("country_code", "49"))
    if raw.get("phonebook"):
        raw["phonebook"] = {normalize(str(k), cc): v for k, v in raw["phonebook"].items()}
    for key in ("sip", "fritz", "notify", "hybrid"):
        if raw.get(key) is None:
            raw.pop(key, None)
    if raw.get("dock_in_call", "ignore") not in ("ignore", "hangup", "handsfree"):
        raise ValueError(f"dock_in_call muss ignore, hangup oder handsfree sein ({path})")
    known = Config.__dataclass_fields__
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"Unbekannte Einstellungen in {path}: {', '.join(sorted(unknown))}")
    return Config(contacts=contacts, **raw)
