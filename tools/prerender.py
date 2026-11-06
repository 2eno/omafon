"""Erzeugt alle festen Ansagen vorab als WAV, damit sie ohne Verzögerung starten.

    sudo -u omafon python3 -m tools.prerender /etc/omafon/config.yaml

Als Dienstbenutzer ausführen, damit die Dateien ihm gehören. Das Telefon rendert
fehlende feste Ansagen auch selbst im Leerlauf nach (neue Kontakte per App,
geänderte Texte) – vorab rendern spart nur die Wartezeit nach der Installation
oder nach einem Stimmenwechsel. Festnetz: lädt zusätzlich die Namen aus dem
Fritz!Box-Telefonbuch.
"""
import asyncio
import sys
import time

from omafon import config
from omafon.audio import Audio
from omafon.phone import fixed_phrases


def load_fritz_phonebook(cfg) -> None:
    """Festnetz: Namen aus dem Fritz!Box-Telefonbuch mit vorab sprechen."""
    if getattr(cfg, "backend", "") != "sip" or not cfg.fritz.get("user"):
        return
    from omafon.fritz import FritzBox
    f = cfg.fritz
    try:
        cfg.phonebook = FritzBox(f.get("host", "fritz.box"), f["user"], f.get("password", ""),
                                 cfg.country_code, int(f.get("tam", 0)),
                                 int(f.get("phonebook_id", 0))).phonebook()
        print(f"Fritz!Box-Telefonbuch: {len(cfg.phonebook)} Nummern")
    except Exception as e:  # Box nicht erreichbar: Kontakte reichen
        print(f"Fritz!Box-Telefonbuch nicht geladen: {e!r}")


def phrases(cfg) -> list[str]:
    """Dieselbe Liste, die Phone im Betrieb dauerhaft im Cache hält."""
    return fixed_phrases(cfg)


async def main(path: str) -> None:
    cfg = config.load(path)
    load_fritz_phonebook(cfg)
    audio = Audio(cfg)
    items = phrases(cfg)
    audio.fixed = set(items)
    t0 = time.monotonic()
    for i, text in enumerate(items, 1):
        ok = await audio.synth(text, keep=True)
        print(f"[{i:3}/{len(items)}] {'ok ' if ok else 'FEHLER'} {text}")
    print(f"Fertig in {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "/etc/omafon/config.yaml"))
