"""Signierte Update-Pakete für das Omafon bauen.

Einmalig Schlüssel erzeugen (privaten Schlüssel NIE committen, sicher aufbewahren):

    python3 -m tools.make_release keygen ~/omafon-signing
    -> ~/omafon-signing/omafon_update.key (privat), Ausgabe: update_public_key für config.yaml

Release bauen (Version aus omafon/__init__.py):

    python3 -m tools.make_release build --key ~/omafon-signing/omafon_update.key \\
        --base-url https://updates.example.org/omafon/ --notes "Was ist neu" --out dist/
    -> dist/omafon-<version>.tar.gz und dist/manifest.json

Beides auf den Webserver legen; update_url in config.yaml zeigt auf manifest.json.
Das Paket enthält nur omafon/*.py – Modelle, Stimmen und Konfiguration bleiben.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        sys.exit("Bitte zuerst: pip install cryptography")
    return serialization, Ed25519PrivateKey


def public_key_b64(key) -> str:
    serialization, _ = _crypto()
    return base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def keygen(directory: Path) -> int:
    serialization, Ed25519PrivateKey = _crypto()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "omafon_update.key"
    if path.exists():
        sys.exit(f"{path} gibt es schon – nicht überschreiben")
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    print(f"Privater Schlüssel: {path}")
    print(f"In config.yaml:     update_public_key: \"{public_key_b64(key)}\"")
    return 0


def package(src: Path = ROOT / "omafon") -> bytes:
    """Reproduzierbares tar.gz (feste Zeiten/Rechte, sortiert)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT) as t:
        for f in sorted(src.glob("*.py")):
            data = f.read_bytes()
            info = tarfile.TarInfo(f"omafon/{f.name}")
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def build(key_path: Path, base_url: str, notes: str, out: Path) -> int:
    serialization, _ = _crypto()
    from omafon import __version__
    from omafon.update import canonical
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    out.mkdir(parents=True, exist_ok=True)
    pkg = package()
    name = f"omafon-{__version__}.tar.gz"
    (out / name).write_bytes(pkg)
    m = {"version": __version__, "url": base_url.rstrip("/") + "/" + name,
         "sha256": hashlib.sha256(pkg).hexdigest(), "notes": notes}
    m["signature"] = base64.b64encode(key.sign(canonical(m))).decode()
    (out / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{out / name}\n{out / 'manifest.json'}  (Version {__version__})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen", help="Signierschlüssel erzeugen")
    k.add_argument("directory", type=Path)
    b = sub.add_parser("build", help="Paket und Manifest bauen")
    b.add_argument("--key", type=Path, required=True)
    b.add_argument("--base-url", required=True, help="Ordner-URL, unter der das Paket liegt")
    b.add_argument("--notes", default="", help="Kurz: was ist neu (zeigt die App an)")
    b.add_argument("--out", type=Path, default=Path("dist"))
    a = ap.parse_args(argv)
    if a.cmd == "keygen":
        return keygen(a.directory)
    return build(a.key, a.base_url, a.notes, a.out)


if __name__ == "__main__":
    sys.exit(main())
