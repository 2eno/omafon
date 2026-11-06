"""Updates mit Rückfall: signierte Pakete, A/B-Installation, automatischer Rollback.

Ablage (beschreibbare Datenpartition, das System selbst ist schreibgeschützt):

    <data_dir>/releases/<version>/     entpackte Versionen
    <data_dir>/current  -> releases/X  Symlink, von dem systemd startet
    <data_dir>/update.json             Zustand: current, previous, pending, boot_attempts

Ablauf einer Installation:
  1. Manifest von update_url laden: {"version", "url", "sha256", "notes", "signature"}.
     signature = Ed25519 über das kanonische JSON der übrigen Felder (sortiert,
     ohne Leerzeichen). Öffentlicher Schlüssel: update_public_key (Base64, 32 Byte).
  2. Paket laden, SHA-256 prüfen, sicher entpacken (keine absoluten Pfade, kein "..").
  3. Rauchtest: die neue Version muss sich importieren lassen.
  4. current -> neue Version, previous merken, pending = neue Version, Neustart.
  5. Beim Start zählt boot() die Versuche. Läuft die neue Version
     CONFIRM_AFTER_S stabil, bestätigt confirm() sie. Nach MAX_BOOTS Starts
     ohne Bestätigung schaltet boot() auf previous zurück.

Kommandozeile (für den Start-Wrapper):  python3 -m omafon.update boot <data_dir>
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("omafon.update")

MAX_BOOTS = 3
CONFIRM_AFTER_S = 120
BASIS = "@basis"            # Erstinstallation unter /opt: Rückfall = Symlink entfernen
MANIFEST_FIELDS = ("version", "url", "sha256", "notes")
MAX_PACKAGE = 50 * 1024 * 1024   # Pakete enthalten nur Python-Code: alles darüber ist kaputt
VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z.+_-]{0,39}$")


class UpdateError(Exception):
    pass


def canonical(manifest: dict) -> bytes:
    """Bytes, über die signiert wird."""
    return json.dumps({k: manifest.get(k, "") for k in MANIFEST_FIELDS},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_signature(manifest: dict, public_key_b64: str) -> None:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError as e:   # auf dem Pi: apt install python3-cryptography
        raise UpdateError("python3-cryptography fehlt – Updates nicht möglich") from e
    if not public_key_b64:
        raise UpdateError("Kein öffentlicher Schlüssel (update_public_key) eingerichtet")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
    except (ValueError, TypeError) as e:
        raise UpdateError("update_public_key ist kein gültiger Ed25519-Schlüssel") from e
    try:
        key.verify(base64.b64decode(str(manifest.get("signature", "")), validate=True), canonical(manifest))
    except (InvalidSignature, ValueError, TypeError) as e:
        raise UpdateError("Signatur ungültig – Paket wird nicht installiert") from e


def version_tuple(v: str) -> tuple:
    out = []
    for part in v.split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


@dataclass
class UpdateState:
    current: str = ""
    previous: str = ""
    pending: str = ""
    boot_attempts: int = 0
    last_error: str = ""
    available: dict = field(default_factory=dict)   # geprüftes Manifest
    phase: str = "idle"        # idle, checking, downloading, verifying, installing, restarting, error


class Updater:
    def __init__(self, data_dir: str | Path, current_version: str, update_url: str | None = None,
                 public_key: str | None = None, opener=None, python: str = sys.executable):
        self.data = Path(data_dir)
        self.releases = self.data / "releases"
        self.link = self.data / "current"
        self.state_file = self.data / "update.json"
        self.update_url = update_url
        self.public_key = public_key
        self.version = current_version
        self._open = opener or (lambda url, timeout: urllib.request.urlopen(url, timeout=timeout))
        self.python = python
        self.state = self.load()
        if not self.state.current:
            self.state.current = current_version

    # ------------------------------------------------------------ Zustand
    def load(self) -> UpdateState:
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            return UpdateState(**{k: v for k, v in raw.items() if k in UpdateState.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return UpdateState()

    def save(self) -> None:
        self.data.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state.__dict__, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def info(self) -> dict:
        s = self.state
        return {"current": self.version, "previous": s.previous, "pending": s.pending,
                "phase": s.phase, "last_error": s.last_error,
                "available": {k: s.available.get(k) for k in ("version", "notes")} if s.available else None,
                "update_available": bool(s.available and version_tuple(s.available["version"])
                                         > version_tuple(self.version)),
                "configured": bool(self.update_url and self.public_key),
                "can_rollback": self._exists(s.previous)}

    def _exists(self, version: str) -> bool:
        return version == BASIS or bool(version and (self.releases / version).is_dir())

    # ------------------------------------------------------------ Prüfen
    def check(self) -> dict:
        if not (self.update_url and self.public_key):
            raise UpdateError("Kein Update-Kanal eingerichtet (update_url, update_public_key)")
        self.state.phase = "checking"
        try:
            with self._open(self.update_url, 20) as r:
                manifest = json.loads(r.read().decode("utf-8"))
            if not isinstance(manifest, dict):
                raise UpdateError("Manifest ist kein JSON-Objekt")
            for k in ("version", "url", "sha256", "signature"):
                if not isinstance(manifest.get(k), str) or not manifest[k]:
                    raise UpdateError(f"Manifest unvollständig: {k} fehlt")
            verify_signature(manifest, self.public_key)
            check_manifest(manifest)
            self.state.available = manifest
            self.state.last_error = ""
            return self.info()
        except UpdateError as e:
            self.state.last_error = str(e)
            raise
        except (OSError, ValueError) as e:
            self.state.last_error = f"Update-Server nicht erreichbar: {e}"
            raise UpdateError(self.state.last_error) from e
        finally:
            self.state.phase = "idle"
            self.save()

    # ------------------------------------------------------------ Installieren
    def install(self) -> str:
        """Lädt, prüft und aktiviert das verfügbare Paket. Rückgabe: neue Version.
        Danach muss der Dienst neu starten (der Aufrufer veranlasst das)."""
        m = self.state.available
        if not m:
            raise UpdateError("Erst nach Updates suchen")
        verify_signature(m, self.public_key)            # nicht auf den alten Stand verlassen
        check_manifest(m)
        version = m["version"]
        # Nie zurück auf eine ältere signierte Version: ein abgefangenes altes
        # Manifest darf keine bekannte Lücke wieder einspielen. Zurück geht nur
        # über rollback() auf die vorherige, schon installierte Version.
        if version_tuple(version) <= version_tuple(self.version):
            raise UpdateError(f"Version {version} ist nicht neuer als {self.version}")
        try:
            self.state.phase = "downloading"
            self.save()
            self.releases.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.data) as tmp:
                pkg = Path(tmp) / "paket.tar.gz"
                h = hashlib.sha256()
                size = 0
                with self._open(m["url"], 60) as r, open(pkg, "wb") as f:
                    while chunk := r.read(65536):
                        size += len(chunk)
                        if size > MAX_PACKAGE:
                            raise UpdateError("Paket ist zu groß")
                        h.update(chunk)
                        f.write(chunk)
                self.state.phase = "verifying"
                if h.hexdigest() != m["sha256"].lower():
                    raise UpdateError("Prüfsumme stimmt nicht – Paket beschädigt")
                staging = Path(tmp) / "neu"
                safe_extract(pkg, staging)
                if not (staging / "omafon" / "__init__.py").exists():
                    raise UpdateError("Paket enthält kein omafon/")
                self.smoke_test(staging, version)
                target = self.releases / version
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(staging), target)
            self.state.phase = "installing"
            self.activate(version)
            # Rückfallziel: die laufende Version – oder die Erstinstallation unter /opt.
            self.state.previous = self.version if (self.releases / self.version).is_dir() else BASIS
            self.state.pending = version
            self.state.boot_attempts = 0
            self.state.phase = "restarting"
            self.state.last_error = ""
            self.save()
            return version
        except UpdateError as e:
            self.state.phase, self.state.last_error = "error", str(e)
            self.save()
            raise
        except (OSError, tarfile.TarError, ValueError) as e:
            self.state.phase, self.state.last_error = "error", f"Installation fehlgeschlagen: {e}"
            self.save()
            raise UpdateError(self.state.last_error) from e

    def smoke_test(self, root: Path, version: str | None = None) -> None:
        try:
            r = subprocess.run([self.python, "-I", "-c", "import sys; sys.path.insert(0, '.'); "
                                "import omafon.phone, omafon.main, omafon.update; print(omafon.__version__)"],
                               cwd=root, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as e:
            raise UpdateError("Neue Version startet nicht (Importtest dauert zu lange)") from e
        if r.returncode != 0:
            raise UpdateError("Neue Version startet nicht (Importtest): "
                              + (r.stderr.strip().splitlines() or ["?"])[-1][:200])
        if version is not None and r.stdout.strip() != version:
            raise UpdateError(f"Paket meldet Version {r.stdout.strip() or '?'} statt {version}")

    def activate(self, version: str) -> None:
        if version == BASIS:                            # Wrapper startet dann /opt/omafon
            if self.link.is_symlink() or self.link.exists():
                self.link.unlink()
            self.state.current = BASIS
            return
        tmp_link = self.data / "current.neu"
        if tmp_link.is_symlink() or tmp_link.exists():
            tmp_link.unlink()
        os.symlink(Path("releases") / version, tmp_link)
        os.replace(tmp_link, self.link)                 # atomar
        self.state.current = version

    # ------------------------------------------------------------ Start / Rückfall
    def boot(self) -> str:
        """Vor jedem Start (Wrapper). Rückgabe: Version, die gestartet wird."""
        s = self.state
        if s.phase != "error":            # Vorgang vom letzten Lauf ist mit dem Neustart vorbei
            s.phase = "idle"
        if s.pending:
            s.boot_attempts += 1
            if s.boot_attempts > MAX_BOOTS:
                # Vorherige Version fehlt (z. B. von Hand gelöscht): die
                # Erstinstallation unter /opt ist immer da – nie auf der kaputten bleiben
                target = s.previous if self._exists(s.previous) else BASIS
                log.error("Version %s startet nicht – zurück zu %s", s.pending, target)
                failed = s.pending
                self.activate(target)
                s.previous, s.pending, s.boot_attempts = "", "", 0
                s.last_error = f"Version {failed} lief nicht stabil – zurück auf {s.current}"
                s.phase = "error"
        self.save()
        return s.current

    def confirm(self) -> None:
        """Neue Version läuft stabil: bestätigen und alte Pakete aufräumen."""
        if not self.state.pending:
            return
        log.info("Version %s bestätigt", self.state.pending)
        self.state.pending, self.state.boot_attempts = "", 0
        self.state.phase = "idle"
        self.save()
        keep = {self.state.current, self.state.previous}
        if self.releases.is_dir():
            for d in self.releases.iterdir():
                if d.is_dir() and d.name not in keep:
                    shutil.rmtree(d, ignore_errors=True)

    def rollback(self) -> str:
        s = self.state
        if not self._exists(s.previous):
            raise UpdateError("Keine ältere Version vorhanden")
        old = s.current
        self.activate(s.previous)
        s.previous, s.pending, s.boot_attempts = old, "", 0
        s.phase = "restarting"
        self.save()
        return s.current


def check_manifest(m: dict) -> None:
    """Felder, die als Pfad oder Prüfsumme benutzt werden, streng prüfen."""
    if not VERSION_RE.match(m.get("version", "")):
        raise UpdateError("Ungültige Versionsnummer im Manifest")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", m.get("sha256", "")):
        raise UpdateError("Ungültige Prüfsumme im Manifest")
    if not str(m.get("url", "")).startswith(("https://", "http://")):
        raise UpdateError("Ungültige Paket-Adresse im Manifest")


def safe_extract(pkg: Path, dest: Path) -> None:
    dest.mkdir(parents=True)
    with tarfile.open(pkg, "r:gz") as t:
        for m in t.getmembers():
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts or m.issym() or m.islnk() or m.isdev():
                raise UpdateError(f"Unsicherer Eintrag im Paket: {m.name}")
        if hasattr(tarfile, "data_filter"):
            t.extractall(dest, filter="data")
        else:                                           # ältere Python-Versionen
            t.extractall(dest)                          # noqa: S202 (oben geprüft)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    if len(argv) >= 3 and argv[1] == "boot":
        from . import __version__
        up = Updater(argv[2], __version__)
        print(up.boot())
        return 0
    print("Aufruf: python3 -m omafon.update boot <data_dir>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
