"""Hilfen rund um Telefonnummern und deutsche Ansagen."""
from __future__ import annotations

import datetime as _dt
import re

# "zwo" statt "zwei": am Telefon nicht mit "drei" zu verwechseln.
DIGIT_WORDS = {
    "0": "null", "1": "eins", "2": "zwo", "3": "drei", "4": "vier",
    "5": "fünf", "6": "sechs", "7": "sieben", "8": "acht", "9": "neun",
    "*": "Stern", "#": "Raute", "+": "plus",
}

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


def normalize(number: str, country_code: str = "49") -> str:
    """+49 171 … / 0049171… / 0171… -> 0171… (nur zum Vergleichen)."""
    n = re.sub(r"[^\d+*#]", "", number or "")
    if n.startswith("+" + country_code):
        n = "0" + n[1 + len(country_code):]
    elif n.startswith("00" + country_code):
        n = "0" + n[2 + len(country_code):]
    return n


def spoken_number(number: str) -> str:
    """'01711234567' -> 'null eins sieben eins, eins zwo drei, vier fünf sechs, sieben'.

    Kommas erzeugen in der Sprachausgabe kurze Pausen.
    """
    chars = [c for c in number if c in DIGIT_WORDS]
    if not chars:
        return "keine Nummer"
    head_len = 4 if chars[0] == "0" and len(chars) > 6 else 3
    groups = [chars[:head_len]] + [chars[i:i + 3] for i in range(head_len, len(chars), 3)]
    return ", ".join(" ".join(DIGIT_WORDS[c] for c in g) for g in groups if g)


def spoken_time(now: _dt.datetime) -> str:
    minute = "" if now.minute == 0 else f" {now.minute}"
    return f"Es ist {now.hour} Uhr{minute}."


def spoken_date(now: _dt.datetime) -> str:
    return f"Heute ist {WEEKDAYS[now.weekday()]}, der {now.day}. {MONTHS[now.month - 1]}."


def signal_words(rssi: int | None) -> str:
    if rssi is None or rssi == 99 or rssi <= 1:
        return "Kein Empfang."
    if rssi < 10:
        return "Empfang schwach."
    if rssi < 20:
        return "Empfang mittel."
    return "Empfang gut."


def count_words(n: int, one: str, many: str, none: str) -> str:
    """count_words(2, 'Eine neue Nachricht', 'neue Nachrichten', 'Keine neuen Nachrichten')"""
    if n == 0:
        return none
    if n == 1:
        return one
    return f"{n} {many}"
