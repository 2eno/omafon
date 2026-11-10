"""Pre-renders all fixed announcements as WAV so they start without delay.

    sudo python3 -m tools.prerender /etc/omafon/config.yaml

Run again after every change to contacts, announcements (P dict) or voice.
Landline: also loads the names from the Fritz!Box phone book.
"""
import asyncio
import sys
import time

from omafon import config
from omafon.audio import Audio
from omafon.numbers import DIGIT_WORDS
from omafon.phone import P


def load_fritz_phonebook(cfg) -> None:
    """Landline: pre-render the names from the Fritz!Box phone book too."""
    if getattr(cfg, "backend", "") != "sip" or not cfg.fritz.get("user"):
        return
    from omafon.fritz import FritzBox
    f = cfg.fritz
    try:
        cfg.phonebook = FritzBox(f.get("host", "fritz.box"), f["user"], f.get("password", ""),
                                 cfg.country_code, int(f.get("tam", 0)),
                                 int(f.get("phonebook_id", 0))).phonebook()
        print(f"Fritz!Box-Telefonbuch: {len(cfg.phonebook)} Nummern")
    except Exception as e:  # box not reachable: the contacts are enough
        print(f"Fritz!Box-Telefonbuch nicht geladen: {e!r}")


def phrases(cfg) -> list[str]:
    out = list(DIGIT_WORDS.values()) + list(P.values())
    out += ["drei", "zwo", "eins"] + [f"Lautstärke {i}." for i in range(1, 6)]
    for d in DIGIT_WORDS.values():
        out.append(f"Auf Taste {d} ist niemand gespeichert.")
    for c in cfg.contacts:
        out += [f"Anruf von {c.name}.", f"Ich rufe {c.name} an.",
                f"{c.name}. Gelbe Taste zum Anrufen.", f"Verpasster Anruf von {c.name}."]
    for name in sorted(set(cfg.phonebook.values())):
        out += [f"Anruf von {name}.", f"Verpasster Anruf von {name}."]
    return list(dict.fromkeys(out))


async def main(path: str) -> None:
    cfg = config.load(path)
    load_fritz_phonebook(cfg)
    audio = Audio(cfg)
    items = phrases(cfg)
    t0 = time.monotonic()
    for i, text in enumerate(items, 1):
        ok = await audio.synth(text)
        print(f"[{i:3}/{len(items)}] {'ok ' if ok else 'FEHLER'} {text}")
    print(f"Fertig in {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "/etc/omafon/config.yaml"))
