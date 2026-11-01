"""Erzeugt alle festen Ansagen vorab als WAV, damit sie ohne Verzögerung starten.

    sudo python3 -m tools.prerender /etc/omafon/config.yaml

Nach jeder Änderung an Kontakten oder Stimme erneut ausführen.
"""
import asyncio
import sys
import time

from omafon import config
from omafon.audio import Audio
from omafon.numbers import DIGIT_WORDS
from omafon.phone import P


def phrases(cfg) -> list[str]:
    out = list(DIGIT_WORDS.values()) + list(P.values())
    out += ["drei", "zwo", "eins"] + [f"Lautstärke {i}." for i in range(1, 6)]
    for d in DIGIT_WORDS.values():
        out.append(f"Auf Taste {d} ist niemand gespeichert.")
    for c in cfg.contacts:
        out += [f"Anruf von {c.name}.", f"Ich rufe {c.name} an.",
                f"{c.name}. Gelbe Taste zum Anrufen.", f"Verpasster Anruf von {c.name}."]
    return list(dict.fromkeys(out))


async def main(path: str) -> None:
    cfg = config.load(path)
    audio = Audio(cfg)
    items = phrases(cfg)
    t0 = time.monotonic()
    for i, text in enumerate(items, 1):
        ok = await audio.synth(text)
        print(f"[{i:3}/{len(items)}] {'ok ' if ok else 'FEHLER'} {text}")
    print(f"Fertig in {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "/etc/omafon/config.yaml"))
