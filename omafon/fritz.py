"""Fritz!Box via TR-064: phone book and answering machine.

Only runs in the LAN against fritz.box. Access: a dedicated Fritz!Box user with
the rights "voice messages, fax messages, FRITZ!App Fon and call list"
(see docs/festnetz-recherche.md). TR-064 must be enabled under Home Network →
Network → Network Settings ("Allow access for applications").

The actual calls are made by the fritzconnection library (SOAP + digest
authentication). Parsing the XML lists lives here as pure functions so it can
be tested without a Fritz!Box.
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
    """A message on the Fritz!Box answering machine."""
    tam: int            # number of the answering machine (0 = first)
    index: int          # message number within the answering machine
    number: str         # caller ("" = withheld)
    name: str           # name from the Fritz!Box phone book ("" = unknown)
    time: dt.datetime | None
    duration: str       # as delivered by the box, e.g. "0:01"
    path: str           # download path (download.lua?path=…)
    new: bool


# ------------------------------------------------------------------ XML
def _text(el, tag: str) -> str:
    found = el.find(tag)
    return (found.text or "").strip() if found is not None else ""


def parse_phonebook(xml_text: str, country_code: str = "49") -> dict[str, str]:
    """Fritz!Box phone book XML -> {normalized number: name}."""
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
    """Response XML of X_AVM-DE_TAM:GetMessageList -> messages (newest first)."""
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
            log.warning("Answering machine entry not readable: %s", ET.tostring(m, encoding="unicode"))
    return out


def download_url(list_url: str, path: str) -> str:
    """Builds the download address of a recording.

    The list URL from GetMessageList contains the session ID (sid). The path
    of the message is either already "/download.lua?path=…" or a plain file
    path ("/data/tam/rec/rec.0.000").
    """
    u = urllib.parse.urlsplit(list_url)
    sid = urllib.parse.parse_qs(u.query).get("sid", [""])[0]
    if not path.startswith("/download.lua"):
        path = "/download.lua?path=" + urllib.parse.quote(path)
    return f"{u.scheme}://{u.netloc}{path}&sid={sid}"


# ------------------------------------------------------------------ Access
class FritzBox:
    """Real Fritz!Box via fritzconnection. All methods block –
    call them from asyncio with run_in_executor."""

    def __init__(self, host: str, user: str, password: str, country_code: str = "49",
                 tam: int = 0, phonebook_id: int = 0, timeout: float = 10):
        self.host, self.user, self.password = host, user, password
        self.country_code, self.tam, self.phonebook_id = country_code, tam, phonebook_id
        self.timeout = timeout
        self._fc = None

    def _conn(self):
        if self._fc is None:
            from fritzconnection import FritzConnection  # only needed on the Pi
            self._fc = FritzConnection(address=self.host, user=self.user,
                                       password=self.password, timeout=self.timeout)
        return self._fc

    def _get(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self.timeout) as r:  # noqa: S310 (LAN only)
            return r.read()

    def phonebook(self) -> dict[str, str]:
        res = self._conn().call_action("X_AVM-DE_OnTel1", "GetPhonebook",
                                       NewPhonebookID=self.phonebook_id)
        return parse_phonebook(self._get(res["NewPhonebookURL"]).decode("utf-8"),
                               self.country_code)

    def tam_messages(self) -> tuple[list[TamMessage], str]:
        """All messages of the answering machine and the list URL (for downloads)."""
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
    """Fritz!Box for the simulator and tests (same methods, everything in memory)."""

    def __init__(self, phonebook: dict[str, str] | None = None, country_code: str = "49"):
        self.country_code = country_code
        self.book = {normalize(k, country_code): v for k, v in (phonebook or {}).items()}
        self.messages: list[TamMessage] = []
        self.audio: dict[int, bytes] = {}
        self.marked: list[int] = []
        self.deleted: list[int] = []
        self.fail = False            # True = Fritz!Box unreachable

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
