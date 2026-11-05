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
    telegram_chat_id: int | str | None = None   # Festnetz: Notruf/Nachrichten per Telegram
    email: str | None = None                    # Festnetz: Notruf/Nachrichten per E-Mail

    def words(self) -> list[str]:
        return [w.lower() for w in (self.spoken or [self.name])]


@dataclass
class Config:
    owner_name: str = "Oma"
    backend: str = "sip"                     # "sip" (Fritz!Box) oder "hybrid" (Fritz!Box + Mobilfunk)
    country_code: str = "49"
    contacts: list[Contact] = field(default_factory=list)
    emergency_ring_seconds: int = 30
    emergency_rounds: int = 2
    emergency_callback_minutes: int = 30
    quiet_hours: tuple[int, int] = (22, 7)
    news_signal_minutes: int = 10            # Gong-Erinnerung bei ungelesenen SMS (0 = nur einmal)
    news_led: bool = True                    # LED blinkt bei ungelesenen SMS
    default_route: str = "earpiece"          # "earpiece" oder "speaker"
    volume: int = 4                          # 1..5
    entry_timeout_s: int = 20
    long_press_s: float = 1.2
    hangup_hold_s: float = 0.5               # im Gespräch: Auflegen erst nach so langem Halten (0 = sofort)
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
    # Festnetz (backend: sip) – Schlüssel siehe omafon/sip.py, fritz.py, notify.py
    sip: dict = field(default_factory=dict)
    fritz: dict = field(default_factory=dict)
    notify: dict = field(default_factory=dict)
    hybrid: dict = field(default_factory=dict)      # Schlüssel siehe omafon/hybrid.py
    # Companion-App und Updates
    admin: dict = field(default_factory=dict)       # enabled, port, bind, tls (omafon/admin.py)
    update_url: str | None = None                   # Manifest des Update-Kanals
    update_public_key: str | None = None            # Ed25519, Base64 (prüft die Signatur)
    phonebook: dict = field(default_factory=dict)   # Nummer -> Name (wird aus der Fritz!Box geladen)
    home_position: list[float] | None = None        # [Breite, Länge] für den Notruf-Hinweis, optional
    link_reminder_minutes: int = 10                  # Verbindung weg: Ansage wiederholen
    # Ladeschale
    answer_on_lift: bool = False             # Abheben aus der Schale nimmt den Anruf an
    dock_in_call: str = "ignore"             # Einstellen im Gespräch: ignore | hangup | handsfree
    dock_speaker: bool = False               # Schale hat Lautsprecher: dort freisprechen

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
        """Name aus den Kontakten, sonst aus dem Fritz!Box-Telefonbuch."""
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
    for key in ("sip", "fritz", "notify", "hybrid", "admin"):
        if raw.get(key) is None:
            raw.pop(key, None)
    if raw.get("dock_in_call", "ignore") not in ("ignore", "hangup", "handsfree"):
        raise ValueError(f"dock_in_call muss ignore, hangup oder handsfree sein ({path})")
    known = Config.__dataclass_fields__
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"Unbekannte Einstellungen in {path}: {', '.join(sorted(unknown))}")
    return Config(contacts=contacts, **raw)
