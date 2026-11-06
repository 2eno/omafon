"""Verwaltungsschnittstelle für die Omafon-App (Android).

HTTPS + JSON im Heimnetz, ohne Zusatzpakete. Die App findet das Gerät per mDNS
(_omafon._tcp, Avahi-Dienstdatei in systemd/) und koppelt sich mit einem
sechsstelligen Code, den das Omafon ansagt (Raute lang drücken). Danach schickt
die App bei jeder Anfrage ihr Token; das Zertifikat merkt sie sich beim Koppeln
(Trust on first use).

Endpunkte (alle unter /api/v1, Antworten JSON):
  GET    /info                ohne Anmeldung: Version, Variante, Koppeln offen?
  POST   /pair                {code, client_name} -> {token, device_id}
  GET    /status              Akku, Verbindung, Zustand, ungelesen, Update
  GET    /settings            Schema + Werte (Kennwörter nur "gesetzt ja/nein")
  PUT    /settings            {values: {schlüssel: wert}} -> {restart}
  GET    /contacts            Kontaktliste
  PUT    /contacts            {contacts: [...]} -> {restart}
  POST   /speak               {text}: Testansage (nur in Ruhe)
  POST   /restart             Dienst neu starten (in Ruhe)
  GET    /update              Update-Zustand
  POST   /update/check        Manifest holen und prüfen
  POST   /update/install      im Hintergrund installieren, danach Neustart
  POST   /update/rollback     zur vorherigen Version
  GET    /clients             gekoppelte Apps
  DELETE /clients/<id>        Kopplung lösen

Änderungen an Einstellungen werden geprüft (config.load auf eine Probedatei),
atomar geschrieben (Sicherung config.yaml.bak) und mit einem Neustart in einer
ruhigen Minute wirksam – nie mitten in einem Gespräch.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import ipaddress
import json
import math
import logging
import os
import re
import secrets
import shutil
import ssl
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import __version__
from . import config as config_mod

log = logging.getLogger("omafon.admin")

API = "/api/v1"
MAX_BODY = 256 * 1024
MAX_CONNECTIONS = 16          # gleichzeitig offene Verbindungen (je bis 15 s)
PAIR_WINDOW_S = 300
PAIR_ATTEMPTS = 5
ADMIN_DEFAULTS = {"enabled": True, "port": 8443, "bind": "0.0.0.0", "tls": True,
                  "allow_public": False}   # True nur, wer weiß, was er tut


# ====================================================================== Schema
@dataclass
class Setting:
    key: str                     # "volume" oder verschachtelt "sip.password"
    type: str                    # int, float, bool, choice, text, secret, hours
    label: str
    group: str
    help: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str = ""
    choices: list = field(default_factory=list)     # [(wert, bezeichnung)]
    variants: tuple = ("sip", "hybrid")
    live: bool = False           # ohne Neustart wirksam
    default: object = None


S = Setting
SETTINGS: list[Setting] = [
    S("owner_name", "text", "Name der Nutzerin", "Allgemein", "Steht in der Notruf-Nachricht."),
    S("volume", "int", "Lautstärke beim Start", "Ton und Sprache", min=1, max=5, step=1, live=True, default=4),
    S("speech_rate", "float", "Sprechtempo", "Ton und Sprache", "1,0 normal, größer = langsamer.",
      min=0.8, max=1.6, step=0.1, default=1.2),
    S("default_route", "choice", "Gespräche hören über", "Ton und Sprache",
      choices=[("earpiece", "Hörer am Ohr"), ("speaker", "Lautsprecher")], default="earpiece"),
    S("long_press_s", "float", "Langer Tastendruck ab", "Tasten", min=0.8, max=2.5, step=0.1, unit="s", default=1.2),
    S("hangup_hold_s", "float", "Auflegen im Gespräch: halten", "Tasten",
      "Schützt davor, mit der Wange aufzulegen. 0 = sofort.", min=0, max=1.5, step=0.1, unit="s", default=0.5),
    S("entry_timeout_s", "int", "Eingabe verwerfen nach", "Tasten", min=10, max=90, step=5, unit="s", default=20),
    S("news_signal_minutes", "int", "Gong für neue Nachrichten alle", "Nachrichten",
      "0 = nur einmal.", min=0, max=60, step=5, unit="min", default=10),
    S("news_led", "bool", "LED blinkt bei neuen Nachrichten", "Nachrichten", default=True),
    S("quiet_hours", "hours", "Ruhezeit (kein Gong, keine Ansagen)", "Nachrichten", default=[22, 7]),
    S("sos_hold_s", "float", "Notrufknopf halten", "Notruf", min=2, max=6, step=0.5, unit="s", default=3.0),
    S("sos_cancel_window_s", "int", "Abbrechen möglich für", "Notruf", min=3, max=15, step=1, unit="s", default=5),
    S("emergency_ring_seconds", "int", "Klingeln je Notfallkontakt", "Notruf", min=15, max=60, step=5, unit="s",
      default=30),
    S("emergency_rounds", "int", "Notrufkette durchlaufen", "Notruf", min=1, max=3, step=1, unit="×", default=2),
    S("emergency_callback_minutes", "int", "Rückrufe automatisch annehmen", "Notruf",
      min=0, max=180, step=10, unit="min", default=30),
    S("answer_on_lift", "bool", "Abheben aus der Schale nimmt an", "Ladeschale", default=False),
    S("dock_in_call", "choice", "Einstellen im Gespräch", "Ladeschale",
      choices=[("hangup", "legt auf"), ("handsfree", "Freisprechen"), ("ignore", "nichts")], default="ignore"),
    S("dock_speaker", "bool", "In der Schale über deren Lautsprecher", "Ladeschale", default=False),
    S("link_reminder_minutes", "int", "Erinnerung „keine Verbindung“ alle", "Verbindung",
      min=0, max=60, step=5, unit="min", default=10),
    S("sip.user", "text", "Benutzername IP-Telefon", "Fritz!Box", "Telefonie → Telefoniegeräte"),
    S("sip.password", "secret", "Kennwort IP-Telefon", "Fritz!Box"),
    S("fritz.user", "text", "Fritz!Box-Benutzer (TR-064)", "Fritz!Box",
      "Recht „Sprachnachrichten, Faxnachrichten, FRITZ!App Fon und Anrufliste“"),
    S("fritz.password", "secret", "Kennwort Fritz!Box-Benutzer", "Fritz!Box"),
    S("fritz.tam", "int", "Anrufbeantworter Nr.", "Fritz!Box", min=0, max=4, step=1, default=0),
    S("notify.enabled", "bool", "Telegram/E-Mail einschalten", "Benachrichtigungen",
      "Notruf-Hinweis und Diktat, wenn keine SMS möglich ist.", default=False),
    S("notify.telegram_token", "secret", "Telegram-Bot-Token", "Benachrichtigungen"),
    S("notify.smtp_host", "text", "E-Mail-Server (SMTP)", "Benachrichtigungen"),
    S("notify.smtp_port", "int", "SMTP-Port", "Benachrichtigungen", min=1, max=65535, step=1, default=587),
    S("notify.smtp_user", "text", "SMTP-Benutzer", "Benachrichtigungen"),
    S("notify.smtp_password", "secret", "SMTP-Kennwort", "Benachrichtigungen"),
    S("notify.smtp_from", "text", "Absenderadresse", "Benachrichtigungen"),
    S("hybrid.prefer", "choice", "Normale Anrufe über", "Hybrid",
      choices=[("home", "Fritz!Box, wenn erreichbar"), ("mobile", "Mobilfunk")], variants=("hybrid",),
      default="home"),
    S("hybrid.home_modem", "choice", "Mobilfunk zu Hause", "Hybrid",
      "„Sparmodus“ braucht eine Rufumleitung beim Anbieter.",
      choices=[("on", "an (Handynummer erreichbar)"), ("off", "Sparmodus")], variants=("hybrid",), default="on"),
    S("hybrid.announce_mode", "bool", "„Zu Hause / Unterwegs“ ansagen", "Hybrid", variants=("hybrid",),
      default=False),
    S("hybrid.weak_wifi_dbm", "int", "Schwaches WLAN ab", "Hybrid",
      "Darunter lieber über Mobilfunk telefonieren.", min=-90, max=-55, step=1, unit="dBm",
      variants=("hybrid",), default=-75),
    S("update_url", "text", "Update-Kanal (Manifest-URL)", "Updates", "Leer = keine Updates."),
]
SETTING_BY_KEY = {s.key: s for s in SETTINGS}


def _get(raw: dict, key: str):
    top, _, sub = key.partition(".")
    if not sub:
        return raw.get(top)
    return (raw.get(top) or {}).get(sub)


def _set(raw: dict, key: str, value) -> None:
    top, _, sub = key.partition(".")
    if not sub:
        if value is None:
            raw.pop(top, None)
        else:
            raw[top] = value
        return
    d = raw.get(top) or {}
    if value is None:
        d.pop(sub, None)
    else:
        d[sub] = value
    raw[top] = d


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def validate_setting(s: Setting, value):
    """Prüft und normalisiert einen Wert. Wirft ApiError(400)."""
    def bad(msg):
        raise ApiError(400, f"{s.label}: {msg}")
    if s.type == "bool":
        if not isinstance(value, bool):
            bad("ja oder nein erwartet")
        return value
    if s.type in ("int", "float"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            bad("Zahl erwartet")
        if isinstance(value, float) and not math.isfinite(value) or isinstance(value, int) and abs(value) > 10**9:
            bad("Zahl erwartet")
        if s.type == "int":
            if int(value) != value:
                bad("ganze Zahl erwartet")
            value = int(value)
        else:
            value = round(float(value), 2)
        if s.min is not None and value < s.min or s.max is not None and value > s.max:
            bad(f"muss zwischen {s.min:g} und {s.max:g} liegen")
        return value
    if s.type == "choice":
        if value not in [c[0] for c in s.choices]:
            bad("unbekannte Auswahl")
        return value
    if s.type in ("text", "secret"):
        if value is not None and not isinstance(value, str):
            bad("Text erwartet")
        value = (value or "").strip()
        if len(value) > 300 or any(ord(c) < 32 for c in value):
            bad("zu lang oder ungültige Zeichen")
        if s.key == "update_url" and value and (not value.startswith(("https://", "http://"))
                                                 or any(c.isspace() for c in value)):
            bad("Adresse muss mit https:// beginnen")
        return value or None
    if s.type == "hours":
        if (not isinstance(value, list) or len(value) != 2
                or not all(isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23 for h in value)):
            bad("zwei Stunden zwischen 0 und 23 erwartet")
        return value
    bad("unbekannter Typ")


_NUMBER = re.compile(r"^\+?[0-9*#]{2,20}$")


def validate_contacts(items) -> list[dict]:
    if not isinstance(items, list) or len(items) > 50:
        raise ApiError(400, "Kontaktliste erwartet (höchstens 50)")
    out, speed, emerg, said = [], set(), set(), {}
    for i, c in enumerate(items, 1):
        if not isinstance(c, dict):
            raise ApiError(400, f"Kontakt {i}: ungültig")
        name = str(c.get("name") or "").strip()
        number = re.sub(r"[\s/()-]", "", str(c.get("number") or ""))
        if not name or len(name) > 40:
            raise ApiError(400, f"Kontakt {i}: Name fehlt oder ist zu lang")
        if not _NUMBER.match(number):
            raise ApiError(400, f"{name}: Telefonnummer ungültig")
        d = {"name": name, "number": number}
        words = c.get("spoken") or []
        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            raise ApiError(400, f"{name}: Sprachwahl-Wörter als Liste erwartet")
        words = [w.strip().lower() for w in words if w.strip()]
        if any(not re.fullmatch(r"[a-zäöüß]{2,20}", w) for w in words):
            raise ApiError(400, f"{name}: Sprachwahl-Wörter nur aus Buchstaben")
        if words:
            d["spoken"] = words
        for w in words or [name.lower()]:      # ohne Wörter zählt der Name (config.Contact.words)
            if w in said and said[w] != name:
                raise ApiError(400, f"„{w}“ steht bei {said[w]} und {name} – Sprachwahl wüsste nicht, wen")
            said[w] = name
        sd = c.get("speed_dial")
        if sd is not None:
            if not isinstance(sd, int) or isinstance(sd, bool) or not 1 <= sd <= 9 or sd in speed:
                raise ApiError(400, f"{name}: Kurzwahl 1–9, jede nur einmal")
            speed.add(sd)
            d["speed_dial"] = sd
        em = c.get("emergency")
        if em is not None:
            if not isinstance(em, int) or isinstance(em, bool) or not 1 <= em <= 20 or em in emerg:
                raise ApiError(400, f"{name}: Platz in der Notrufkette 1–20, jeder nur einmal")
            emerg.add(em)
            d["emergency"] = em
        if c.get("admin"):
            d["admin"] = True
        for k in ("telegram_chat_id", "email"):
            v = c.get(k)
            if v not in (None, ""):
                if not isinstance(v, (str, int)) or isinstance(v, bool) or len(str(v)) > 100:
                    raise ApiError(400, f"{name}: {k} ungültig")
                d[k] = v
        out.append(d)
    return out


# ====================================================================== Zustand
@dataclass
class Client:
    id: str
    name: str
    token_hash: str
    created: str
    last_seen: str = ""


class AdminServer:
    def __init__(self, cfg, config_path: str | Path, phone=None, updater=None, clock=time.time):
        self.cfg = cfg
        self.config_path = Path(config_path)
        self.phone, self.updater = phone, updater
        self.opts = {**ADMIN_DEFAULTS, **(getattr(cfg, "admin", None) or {})}
        self.dir = Path(cfg.data_dir) / "admin"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.started = clock()
        self.device_id = self._device_id()
        self.clients = self._load_clients()
        self.pair_code: str | None = None
        self.pair_until = 0.0
        self.pair_attempts = 0
        self.server: asyncio.base_events.Server | None = None
        self.port = int(self.opts["port"])
        self._bg: set[asyncio.Task] = set()
        self._open = 0

    # ------------------------------------------------------------ Dateien
    def _device_id(self) -> str:
        f = self.dir / "device_id"
        try:
            return f.read_text().strip()
        except OSError:
            did = str(uuid.uuid4())
            f.write_text(did)
            return did

    def _load_clients(self) -> list[Client]:
        try:
            return [Client(**c) for c in json.loads((self.dir / "clients.json").read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []

    def _save_clients(self) -> None:
        tmp = self.dir / "clients.json.tmp"
        tmp.write_text(json.dumps([c.__dict__ for c in self.clients], ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.dir / "clients.json")

    def tls_context(self) -> ssl.SSLContext:
        cert, key = self.dir / "cert.pem", self.dir / "key.pem"
        if not (cert.exists() and key.exists()):
            subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                            "ec_paramgen_curve:prime256v1", "-nodes", "-days", "3650",
                            "-subj", "/CN=omafon", "-keyout", str(key), "-out", str(cert)],
                           check=True, capture_output=True)
            os.chmod(key, 0o600)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        return ctx

    def fingerprint(self) -> str:
        pem = (self.dir / "cert.pem").read_text()
        return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()

    # ------------------------------------------------------------ Koppeln
    def open_pairing(self) -> str:
        self.pair_code = f"{secrets.randbelow(1_000_000):06d}"
        self.pair_until = self.clock() + PAIR_WINDOW_S
        self.pair_attempts = 0
        log.info("Koppeln offen für %d s", PAIR_WINDOW_S)
        return self.pair_code

    @property
    def pairing_open(self) -> bool:
        return bool(self.pair_code) and self.clock() < self.pair_until

    def pair(self, code: str, client_name: str) -> dict:
        if not self.pairing_open:
            raise ApiError(403, "Koppeln ist nicht offen – am Omafon die Raute-Taste lang drücken")
        self.pair_attempts += 1
        if not secrets.compare_digest(str(code).strip(), self.pair_code):
            if self.pair_attempts >= PAIR_ATTEMPTS:
                self.pair_code = None                    # zu viele Versuche: neu öffnen
                raise ApiError(403, "Zu viele falsche Codes – Koppeln neu starten")
            raise ApiError(403, "Code falsch")
        token = secrets.token_urlsafe(32)
        name = (str(client_name or "App").strip() or "App")[:40]
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.clients.append(Client(str(uuid.uuid4()), name, _hash(token), now, now))
        self._save_clients()
        self.pair_code = None
        if self.phone is not None:
            self.phone.paired(name)
        return {"token": token, "device_id": self.device_id, "client_id": self.clients[-1].id}

    def authenticate(self, headers: dict) -> Client:
        auth = headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            raise ApiError(401, "Nicht angemeldet")
        h = _hash(auth[7:].strip())
        for c in self.clients:
            if secrets.compare_digest(c.token_hash, h):
                now = dt.datetime.now().isoformat(timespec="seconds")
                stale = c.last_seen[:15] != now[:15]     # höchstens alle 10 Minuten speichern
                c.last_seen = now
                if stale:
                    try:
                        self._save_clients()
                    except OSError as e:
                        log.warning("clients.json: %s", e)
                return c
        raise ApiError(401, "Unbekannte App – bitte neu koppeln")

    # ------------------------------------------------------------ Antworten
    def info(self) -> dict:
        return {"app": "omafon", "api": 1, "version": __version__, "device_id": self.device_id,
                "variant": self.cfg.backend, "pairing_open": self.pairing_open}

    def status(self) -> dict:
        p = self.phone
        out = {"version": __version__, "variant": self.cfg.backend, "owner_name": self.cfg.owner_name,
               "uptime_s": int(self.clock() - self.started)}
        if p is not None:
            m, hw = p.modem, p.hw
            out.update({
                "state": p.state.name.lower(), "battery": hw.battery_percent(), "charging": hw.on_charger(),
                "online": m.online, "connection": m.status_words() or "",
                "unread": sum(not x["read"] for x in p.inbox), "missed": len(p.missed),
                "restart_pending": bool(p.restart_reason), "time_known": bool(p.time_known())})
        if self.updater is not None:
            out["update"] = self.updater.info()
        return out

    def raw_config(self) -> dict:
        return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}

    def settings(self) -> dict:
        raw = self.raw_config()
        variant = raw.get("backend", self.cfg.backend)
        groups: dict[str, list] = {}
        for s in SETTINGS:
            if variant not in s.variants:
                continue
            v = _get(raw, s.key)
            item = {"key": s.key, "type": s.type, "label": s.label, "help": s.help, "unit": s.unit,
                    "min": s.min, "max": s.max, "step": s.step, "live": s.live,
                    "choices": [{"value": c[0], "label": c[1]} for c in s.choices]}
            if s.type == "secret":
                item["value"], item["is_set"] = None, bool(v)
            else:
                item["value"] = s.default if v is None else v
                if s.type == "hours" and isinstance(item["value"], tuple):
                    item["value"] = list(item["value"])
                if s.type == "choice" and isinstance(item["value"], bool):
                    item["value"] = "on" if item["value"] else "off"   # YAML: on/off ohne Anführungszeichen
            groups.setdefault(s.group, []).append(item)
        return {"variant": variant, "groups": [{"title": t, "items": i} for t, i in groups.items()]}

    def put_settings(self, values: dict) -> dict:
        if not isinstance(values, dict) or not values:
            raise ApiError(400, "Keine Änderungen")
        raw = self.raw_config()
        variant = raw.get("backend", self.cfg.backend)
        live_only = True
        for key, value in values.items():
            s = SETTING_BY_KEY.get(key)
            if s is None or variant not in s.variants:
                raise ApiError(400, f"Unbekannte Einstellung: {key}")
            if s.type == "secret" and value is None:
                continue                                 # unverändert lassen
            _set(raw, key, validate_setting(s, value))
            live_only = live_only and s.live
        self.write_config(raw)
        if live_only and self.phone is not None and "volume" in values:
            self.phone.audio.set_volume(int(values["volume"]))
            return {"restart": False}
        self.request_restart("settings_restart")
        return {"restart": True}

    def contacts(self) -> dict:
        return {"contacts": self.raw_config().get("contacts") or []}

    def put_contacts(self, items) -> dict:
        raw = self.raw_config()
        raw["contacts"] = validate_contacts(items)
        self.write_config(raw)
        self.request_restart("settings_restart")
        return {"restart": True}

    def write_config(self, raw: dict) -> None:
        """Prüfen (wie beim Start), dann atomar ersetzen. Alte Fassung -> .bak"""
        text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=None)
        probe = self.config_path.with_suffix(".probe.yaml")
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # enthält Kennwörter
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            config_mod.load(probe)
        except (ValueError, TypeError) as e:
            raise ApiError(400, f"Einstellungen ungültig: {e}") from e
        finally:
            probe.unlink(missing_ok=True)
        shutil.copy2(self.config_path, self.config_path.with_suffix(".yaml.bak"))
        tmp = self.config_path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)     # nie kurz lesbar
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o600)                             # falls die Datei schon da war
        os.replace(tmp, self.config_path)
        log.info("Einstellungen gespeichert")

    def request_restart(self, phrase_key: str) -> None:
        if self.phone is not None:
            self.phone.request_restart(phrase_key)

    # ------------------------------------------------------------ Updates
    def _update_idle(self) -> None:
        if self.updater.state.phase not in ("idle", "error"):
            raise ApiError(409, "Update läuft gerade")

    async def update_check(self) -> dict:
        from .update import UpdateError
        self._update_idle()
        try:
            return await asyncio.get_running_loop().run_in_executor(None, self.updater.check)
        except UpdateError as e:
            raise ApiError(502, str(e)) from e

    def update_install(self) -> dict:
        info = self.updater.info()
        if info["phase"] not in ("idle", "error"):
            raise ApiError(409, "Update läuft schon")
        if not info["update_available"]:
            raise ApiError(409, "Kein neueres Update verfügbar")
        self.updater.state.phase = "downloading"
        t = asyncio.create_task(self._install())
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)
        return self.updater.info()

    async def _install(self) -> None:
        from .update import UpdateError
        try:
            await asyncio.get_running_loop().run_in_executor(None, self.updater.install)
            self.request_restart("update_restart")
        except UpdateError as e:
            log.error("Update fehlgeschlagen: %s", e)
            if self.phone is not None:
                self.phone.speak_key("update_failed")

    def update_rollback(self) -> dict:
        from .update import UpdateError
        self._update_idle()
        try:
            self.updater.rollback()
        except UpdateError as e:
            raise ApiError(409, str(e)) from e
        self.request_restart("update_restart")
        return self.updater.info()

    # ------------------------------------------------------------ HTTP
    async def start(self) -> None:
        ctx = self.tls_context() if self.opts.get("tls", True) else None
        self.server = await asyncio.start_server(self._client, self.opts["bind"], self.port, ssl=ctx)
        self.port = self.server.sockets[0].getsockname()[1]
        log.info("Verwaltung auf Port %d (%s)", self.port, "HTTPS" if ctx else "HTTP")

    async def stop(self) -> None:
        if self.server:
            self.server.close()

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        if not local_peer(peer[0] if peer else "", self.opts.get("allow_public", False)):
            log.warning("Verwaltung: Verbindung von %s abgelehnt (nicht im Heimnetz)", peer)
            writer.close()
            return
        if self._open >= MAX_CONNECTIONS:          # niemand soll die Verwaltung zustopfen
            log.warning("Verwaltung: zu viele Verbindungen, %s abgewiesen", peer)
            writer.close()
            return
        self._open += 1
        try:
            await self._serve(reader, writer)
        finally:
            self._open -= 1

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        status, body = 500, {"error": "Interner Fehler"}
        try:
            method, path, headers, data = await asyncio.wait_for(_read_request(reader), 15)
            status, body = 200, await self.handle(method, path, headers, data)
        except ApiError as e:
            status, body = e.status, {"error": e.message}
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, ValueError):
            status, body = 400, {"error": "Ungültige Anfrage"}
        except Exception:
            log.exception("Verwaltung")
        try:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            writer.write(f"HTTP/1.1 {status} {_REASON.get(status, 'OK')}\r\n"
                         f"Content-Type: application/json; charset=utf-8\r\n"
                         f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode() + payload)
            await writer.drain()
        except (ConnectionError, ssl.SSLError):
            pass
        finally:
            writer.close()

    async def handle(self, method: str, path: str, headers: dict, data: bytes) -> dict:
        if not path.startswith(API + "/"):
            raise ApiError(404, "Unbekannter Pfad")
        route = path[len(API):].split("?")[0].rstrip("/")
        body = {}
        if data:
            try:
                body = json.loads(data.decode("utf-8"), parse_constant=_no_constant)
            except ValueError as e:                      # auch UnicodeDecodeError
                raise ApiError(400, "JSON erwartet") from e
            if not isinstance(body, dict):
                raise ApiError(400, "JSON-Objekt erwartet")
        if method == "GET" and route == "/info":
            return self.info()
        if method == "POST" and route == "/pair":
            return self.pair(body.get("code", ""), body.get("client_name", ""))
        client = self.authenticate(headers)
        if method == "GET" and route == "/status":
            return self.status()
        if method == "GET" and route == "/settings":
            return self.settings()
        if method == "PUT" and route == "/settings":
            return self.put_settings(body.get("values"))
        if method == "GET" and route == "/contacts":
            return self.contacts()
        if method == "PUT" and route == "/contacts":
            return self.put_contacts(body.get("contacts"))
        if method == "POST" and route == "/speak":
            text = str(body.get("text") or "").strip()
            if not text or len(text) > 200:
                raise ApiError(400, "Text mit 1–200 Zeichen erwartet")
            if self.phone is None or not self.phone.idle():
                raise ApiError(409, "Das Telefon ist gerade beschäftigt")
            self.phone.speak(text)
            return {"ok": True}
        if method == "POST" and route == "/restart":
            self.request_restart("settings_restart")
            return {"ok": True}
        if route.startswith("/update"):
            if self.updater is None:
                raise ApiError(404, "Updates nicht verfügbar")
            if method == "GET" and route == "/update":
                return self.updater.info()
            if method == "POST" and route == "/update/check":
                return await self.update_check()
            if method == "POST" and route == "/update/install":
                return self.update_install()
            if method == "POST" and route == "/update/rollback":
                return self.update_rollback()
        if method == "GET" and route == "/clients":
            return {"clients": [{"id": c.id, "name": c.name, "created": c.created, "last_seen": c.last_seen,
                                 "this": c.id == client.id} for c in self.clients]}
        if method == "DELETE" and route.startswith("/clients/"):
            cid = route.split("/")[-1]
            before = len(self.clients)
            self.clients = [c for c in self.clients if c.id != cid]
            if len(self.clients) == before:
                raise ApiError(404, "Unbekannte App")
            self._save_clients()
            return {"ok": True}
        raise ApiError(404, "Unbekannter Pfad")


_REASON = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
           409: "Conflict", 500: "Internal Server Error", 502: "Bad Gateway"}


def local_peer(ip: str, allow_public: bool = False) -> bool:
    """Nur Heimnetz/VPN: private, Link-lokale und Loopback-Adressen. Schützt, falls
    das Gerät doch einmal öffentlich erreichbar ist (Mobilfunk-Daten, Portfreigabe)."""
    if allow_public:
        return True
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return a.is_private or a.is_link_local or a.is_loopback


def _no_constant(name: str):
    raise ValueError(f"{name} ist keine Zahl")          # NaN/Infinity: JSON erlaubt sie nicht


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _read_request(reader: asyncio.StreamReader):
    line = (await reader.readline()).decode("latin-1").strip()
    method, path, _version = line.split(" ", 2)
    headers = {}
    while True:
        h = (await reader.readline()).decode("latin-1")
        if h in ("\r\n", "\n", ""):
            break
        k, _, v = h.partition(":")
        headers[k.strip().lower()] = v.strip()
        if len(headers) > 50:
            raise ValueError("zu viele Kopfzeilen")
    n = int(headers.get("content-length", "0") or 0)
    if n > MAX_BODY:
        raise ApiError(400, "Anfrage zu groß")
    data = await reader.readexactly(n) if n else b""
    return method.upper(), path, headers, data
