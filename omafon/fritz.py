"""Fritz!Box per TR-064: Telefonbuch und Anrufbeantworter.

Läuft nur im LAN gegen fritz.box. Zugang: eigener Fritz!Box-Benutzer mit den
Rechten "Sprachnachrichten, Faxnachrichten, FRITZ!App Fon und Anrufliste"
(siehe docs/festnetz-recherche.md). TR-064 muss unter Heimnetz → Netzwerk →
Netzwerkeinstellungen ("Zugriff für Anwendungen zulassen") eingeschaltet sein.

Die eigentlichen Aufrufe macht die Bibliothek fritzconnection (SOAP + Digest-
Anmeldung). Die Auswertung der XML-Listen steht hier als reine Funktionen,
damit sie ohne Fritz!Box testbar ist.
"""
from __future__ import annotations

import datetime as dt
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .numbers import normalize

log = logging.getLogger("omafon.fritz")


@dataclass
class TamMessage:
    """Eine Nachricht auf dem Fritz!Box-Anrufbeantworter."""
    tam: int            # Nummer des Anrufbeantworters (0 = erster)
    index: int          # Nachrichtennummer innerhalb des AB
    number: str         # Anrufer ("" = unterdrückt)
    name: str           # Name laut Fritz!Box-Telefonbuch ("" = unbekannt)
    time: dt.datetime | None
    duration: str       # wie von der Box geliefert, z. B. "0:01"
    path: str           # Download-Pfad (download.lua?path=…)
    new: bool


# ------------------------------------------------------------------ XML
def _text(el, tag: str) -> str:
    found = el.find(tag)
    return (found.text or "").strip() if found is not None else ""


def parse_phonebook(xml_text: str, country_code: str = "49") -> dict[str, str]:
    """Fritz!Box-Telefonbuch-XML -> {normalisierte Nummer: Name}."""
    out: dict[str, str] = {}
    root = ET.fromstring(xml_text)
    for contact in root.iter("contact"):
        name = _text(contact, "person/realName")
        if not name:
            continue
        for num in contact.iter("number"):
            n = normalize((num.text or "").strip(), country_code)
            if n:
                out.setdefault(n, name)
    return out


def _parse_date(text: str) -> dt.datetime | None:
    for fmt in ("%d.%m.%y %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def parse_tam_list(xml_text: str) -> list[TamMessage]:
    """Antwort-XML von X_AVM-DE_TAM:GetMessageList -> Nachrichten (neueste zuerst)."""
    out = []
    root = ET.fromstring(xml_text)
    for m in root.iter("Message"):
        try:
            out.append(TamMessage(
                tam=int(_text(m, "Tam") or 0), index=int(_text(m, "Index")),
                number=_text(m, "Number"), name=_text(m, "Name"),
                time=_parse_date(_text(m, "Date")), duration=_text(m, "Duration"),
                path=_text(m, "Path"), new=_text(m, "New") == "1"))
        except ValueError:
            log.warning("AB-Eintrag nicht lesbar: %s", ET.tostring(m, encoding="unicode"))
    return out


def download_url(list_url: str, path: str) -> str:
    """Baut die Download-Adresse einer Aufnahme.

    Die Listen-URL von GetMessageList enthält die Sitzungs-ID (sid). Der Pfad
    der Nachricht ist entweder schon "/download.lua?path=…" oder ein reiner
    Dateipfad ("/data/tam/rec/rec.0.000").
    """
    u = urllib.parse.urlsplit(list_url)
    sid = urllib.parse.parse_qs(u.query).get("sid", [""])[0]
    if not path.startswith("/download.lua"):
        path = "/download.lua?path=" + urllib.parse.quote(path)
    return f"{u.scheme}://{u.netloc}{path}&sid={sid}"


# ------------------------------------------------------------------ Zugriff
class FritzBox:
    """Echte Fritz!Box über fritzconnection. Alle Methoden blockieren –
    aus asyncio heraus mit run_in_executor aufrufen."""

    def __init__(self, host: str, user: str, password: str, country_code: str = "49",
                 tam: int = 0, phonebook_id: int = 0, timeout: float = 10):
        self.host, self.user, self.password = host, user, password
        self.country_code, self.tam, self.phonebook_id = country_code, tam, phonebook_id
        self.timeout = timeout
        self._fc = None

    def _conn(self):
        if self._fc is None:
            from fritzconnection import FritzConnection  # nur auf dem Pi nötig
            self._fc = FritzConnection(address=self.host, user=self.user,
                                       password=self.password, timeout=self.timeout)
        return self._fc

    def _get(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self.timeout) as r:  # noqa: S310 (nur LAN)
            return r.read()

    def phonebook(self) -> dict[str, str]:
        res = self._conn().call_action("X_AVM-DE_OnTel1", "GetPhonebook",
                                       NewPhonebookID=self.phonebook_id)
        return parse_phonebook(self._get(res["NewPhonebookURL"]).decode("utf-8"),
                               self.country_code)

    def tam_messages(self) -> tuple[list[TamMessage], str]:
        """Alle Nachrichten des AB und die Listen-URL (für Downloads)."""
        res = self._conn().call_action("X_AVM-DE_TAM1", "GetMessageList", NewIndex=self.tam)
        url = res["NewURL"]
        return parse_tam_list(self._get(url).decode("utf-8")), url

    def download(self, list_url: str, msg: TamMessage) -> bytes:
        return self._get(download_url(list_url, msg.path))

    def mark_read(self, msg: TamMessage) -> None:
        self._conn().call_action("X_AVM-DE_TAM1", "MarkMessage", NewIndex=msg.tam,
                                 NewMessageIndex=msg.index, NewMarkedAsRead=1)

    def delete(self, msg: TamMessage) -> None:
        self._conn().call_action("X_AVM-DE_TAM1", "DeleteMessage", NewIndex=msg.tam,
                                 NewMessageIndex=msg.index)


class SimFritzBox:
    """Fritz!Box für Simulator und Tests (gleiche Methoden, alles im Speicher)."""

    def __init__(self, phonebook: dict[str, str] | None = None, country_code: str = "49"):
        self.country_code = country_code
        self.book = {normalize(k, country_code): v for k, v in (phonebook or {}).items()}
        self.messages: list[TamMessage] = []
        self.audio: dict[int, bytes] = {}
        self.marked: list[int] = []
        self.deleted: list[int] = []
        self.fail = False            # True = Fritz!Box nicht erreichbar

    def _check(self):
        if self.fail:
            raise OSError("Fritz!Box nicht erreichbar (Simulation)")

    def add_message(self, number: str, audio: bytes, name: str = "",
                    when: dt.datetime | None = None) -> TamMessage:
        idx = max((m.index for m in self.messages), default=-1) + 1
        m = TamMessage(0, idx, number, name, when or dt.datetime(2026, 11, 1, 18, 0),
                       "0:01", f"/download.lua?path=/data/tam/rec/rec.0.{idx:03}", True)
        self.messages.insert(0, m)
        self.audio[idx] = audio
        return m

    def phonebook(self) -> dict[str, str]:
        self._check()
        return dict(self.book)

    def tam_messages(self) -> tuple[list[TamMessage], str]:
        self._check()
        return list(self.messages), "http://fritz.box:49000/tamcalllist.lua?sid=0000&tamindex=0"

    def download(self, list_url: str, msg: TamMessage) -> bytes:
        self._check()
        return self.audio[msg.index]

    def mark_read(self, msg: TamMessage) -> None:
        self._check()
        msg.new = False
        self.marked.append(msg.index)

    def delete(self, msg: TamMessage) -> None:
        self._check()
        self.messages = [m for m in self.messages if m.index != msg.index]
        self.deleted.append(msg.index)
