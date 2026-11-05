"""JSON-Beispiele der Verwaltungsschnittstelle für die Tests der Android-App.

    python3 -m tools.api_fixtures      # schreibt android/app/src/test/resources/api/*.json

tests/test_admin.py prüft, dass die Dateien zur Schnittstelle passen. Ändert sich
die Schnittstelle, diesen Befehl laufen lassen und die App-Tests anpassen.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "android" / "app" / "src" / "test" / "resources" / "api"
sys.path.insert(0, str(ROOT))

DEVICE_ID = "00000000-0000-4000-8000-000000000000"
CLIENT_ID = "11111111-1111-4111-8111-111111111111"
STAMP = "2026-11-05T15:00:00"


async def _collect(tmp: Path) -> dict:
    from omafon import config
    from omafon.admin import AdminServer
    from omafon.audio import SimAudio
    from omafon.hardware import SimHardware
    from omafon.modem import SimModem
    from omafon.phone import Phone
    from omafon.stt import SimRecognizer
    from omafon.update import Updater

    out = {}
    for variant in ("festnetz", "hybrid"):
        d = tmp / variant
        d.mkdir()
        cfg_path = d / "config.yaml"
        shutil.copy(ROOT / f"config.{variant}.example.yaml", cfg_path)
        cfg = config.load(cfg_path)
        cfg.data_dir = str(d / "data")
        q: asyncio.Queue = asyncio.Queue()
        phone = Phone(cfg, SimAudio(cfg, echo=False), SimModem(q, echo=False), SimRecognizer(),
                      SimHardware(cfg, q, echo=False), q, clock=lambda: dt.datetime(2026, 11, 5, 15, 0))
        await phone.startup()
        up = Updater(d / "data", "0.9.0", "https://updates.example.invalid/omafon.json", "PLATZHALTER")
        up.state.available = {"version": "0.10.0", "url": "https://updates.example.invalid/0.10.0.tar.gz",
                              "sha256": "0" * 64, "notes": "Beispiel: Ansagen klarer, Akku hält länger.",
                              "signature": "PLATZHALTER"}
        admin = AdminServer(cfg, cfg_path, phone, up, clock=lambda: 1000.0)
        admin.device_id = DEVICE_ID
        phone.cancel_job()
        out[f"settings_{variant}.json"] = admin.settings()
        if variant == "festnetz":
            info = admin.info()
            info["pairing_open"] = True
            out["info.json"] = info
            status = admin.status()
            info["version"] = status["version"] = "0.9.0"       # unabhängig von __version__
            out["status.json"] = status
            out["contacts.json"] = admin.contacts()
            out["update.json"] = up.info()
            out["pair.json"] = {"token": "PLATZHALTER_TOKEN", "device_id": DEVICE_ID, "client_id": CLIENT_ID}
            out["clients.json"] = {"clients": [{"id": CLIENT_ID, "name": "Pixel 8", "created": STAMP,
                                                "last_seen": STAMP, "this": True}]}
    return out


def fixtures() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(_collect(Path(tmp))) if not _in_loop() else _run_in_thread(Path(tmp))


def _in_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _run_in_thread(tmp: Path) -> dict:
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(lambda: asyncio.run(_collect(tmp))).result()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(OUT / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
