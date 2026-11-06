"""Tests für die Verwaltungsschnittstelle (Companion-App) und die Updates."""
import asyncio
import base64
import datetime as dt
import hashlib
import io
import json
import shutil
import ssl
import sys
import tarfile
import tempfile
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omafon import __version__, config
from omafon.admin import AdminServer, ApiError, validate_contacts
from omafon.audio import SimAudio
from omafon.hardware import SimHardware
from omafon.modem import SimModem
from omafon.phone import P, Phone
from omafon.stt import SimRecognizer
from omafon.update import BASIS, MAX_BOOTS, UpdateError, Updater, canonical

ROOT = Path(__file__).resolve().parents[1]

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


class AdminBase(unittest.IsolatedAsyncioTestCase):
    variant = "festnetz"

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.cfg_path = d / "config.yaml"
        shutil.copy(ROOT / f"config.{self.variant}.example.yaml", self.cfg_path)
        self.cfg = config.load(self.cfg_path)
        self.cfg.data_dir = str(d / "data")
        self.t = 1000.0
        self.q = asyncio.Queue()
        self.audio = SimAudio(self.cfg, echo=False)
        self.hw = SimHardware(self.cfg, self.q, echo=False)
        self.modem = SimModem(self.q, echo=False)
        self.phone = Phone(self.cfg, self.audio, self.modem, SimRecognizer(), self.hw, self.q,
                           clock=lambda: dt.datetime(2026, 11, 5, 15, 0))
        await self.phone.startup()
        self.phone.pause_s = 0.01
        self.audio.spoken.clear()
        self.admin = AdminServer(self.cfg, self.cfg_path, self.phone, clock=lambda: self.t)
        self.phone.admin = self.admin

    async def asyncTearDown(self):
        self.phone.cancel_job()
        self.tmp.cleanup()

    async def pump(self, rounds=30):
        for _ in range(rounds):
            while not self.q.empty():
                await self.phone.handle(self.q.get_nowait())
            await asyncio.sleep(0.005)

    async def _until(self, cond, timeout=2.0):
        for _ in range(int(timeout / 0.01)):
            if cond():
                return True
            await self.pump(1)
            await asyncio.sleep(0.01)
        return cond()

    def token(self) -> str:
        code = self.admin.open_pairing()
        return self.admin.pair(code, "Testhandy")["token"]

    def auth(self, token):
        return {"authorization": f"Bearer {token}"}


class PairingTests(AdminBase):
    async def test_pairing_flow(self):
        with self.assertRaises(ApiError) as e:
            self.admin.pair("123456", "x")
        self.assertEqual(e.exception.status, 403)           # nicht offen
        code = self.admin.open_pairing()
        self.assertRegex(code, r"^\d{6}$")
        with self.assertRaises(ApiError):
            self.admin.pair("000000" if code != "000000" else "111111", "x")
        res = self.admin.pair(code, "Peters Handy")
        self.assertEqual(res["device_id"], self.admin.device_id)
        self.assertFalse(self.admin.pairing_open)           # Code nur einmal gültig
        self.assertEqual(self.admin.authenticate(self.auth(res["token"])).name, "Peters Handy")
        with self.assertRaises(ApiError) as e:
            self.admin.authenticate(self.auth("falsch"))
        self.assertEqual(e.exception.status, 401)
        stored = (Path(self.cfg.data_dir) / "admin" / "clients.json").read_text()
        self.assertNotIn(res["token"], stored)              # nur der Hash liegt auf dem Gerät
        await self.pump()
        self.assertIn(P["pair_done"], " | ".join(self.audio.spoken))

    async def test_pairing_window_and_attempts(self):
        code = self.admin.open_pairing()
        self.t += 301
        with self.assertRaises(ApiError):
            self.admin.pair(code, "x")                       # abgelaufen
        code = self.admin.open_pairing()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            with self.assertRaises(ApiError):
                self.admin.pair(wrong, "x")
        with self.assertRaises(ApiError):
            self.admin.pair(code, "x")                       # nach 5 Fehlversuchen gesperrt

    async def test_long_hash_announces_code(self):
        self.hw.press("#", long=True)
        await self.pump(60)
        said = " | ".join(self.audio.spoken)
        self.assertIn(P["pair_intro"], said)
        self.assertIn(P["pair_again"], said)
        from omafon.numbers import DIGIT_WORDS
        digits = " | ".join(DIGIT_WORDS[d] for d in self.admin.pair_code)
        self.assertEqual(said.count(digits), 2, said)          # Code zweimal, Ziffer für Ziffer

    async def test_clients_list_and_unpair(self):
        tok = self.token()
        other = self.token()
        res = await self.admin.handle("GET", "/api/v1/clients", self.auth(tok), b"")
        self.assertEqual(len(res["clients"]), 2)
        mine = next(c for c in res["clients"] if c["this"])
        theirs = next(c for c in res["clients"] if not c["this"])
        await self.admin.handle("DELETE", f"/api/v1/clients/{theirs['id']}", self.auth(tok), b"")
        with self.assertRaises(ApiError):
            await self.admin.handle("GET", "/api/v1/status", self.auth(other), b"")
        self.assertTrue(mine["id"])


class SettingsTests(AdminBase):
    async def test_schema_hides_secrets_and_follows_variant(self):
        s = self.admin.settings()
        self.assertEqual(s["variant"], "sip")
        titles = [g["title"] for g in s["groups"]]
        self.assertIn("Fritz!Box", titles)
        self.assertNotIn("Hybrid", titles)
        items = {i["key"]: i for g in s["groups"] for i in g["items"]}
        self.assertIsNone(items["sip.password"]["value"])
        self.assertTrue(items["sip.password"]["is_set"])
        self.assertNotIn("PLATZHALTER", json.dumps(s))
        self.assertEqual(items["quiet_hours"]["value"], [22, 7])
        self.assertEqual(items["volume"]["value"], 4)

    async def test_change_is_validated_written_and_restarts_when_idle(self):
        res = self.admin.put_settings({"hangup_hold_s": 0.8, "quiet_hours": [21, 8],
                                       "sip.password": None})
        self.assertTrue(res["restart"])
        cfg = config.load(self.cfg_path)
        self.assertEqual(cfg.hangup_hold_s, 0.8)
        self.assertEqual(cfg.quiet_hours, (21, 8))
        self.assertEqual(cfg.sip["password"], "PLATZHALTER_SIP_KENNWORT")   # None = unverändert
        self.assertTrue(self.cfg_path.with_suffix(".yaml.bak").exists())
        await self.pump()
        self.assertTrue(await self._until(lambda: self.phone.restart_event.is_set()))
        self.assertIn(P["settings_restart"], self.audio.spoken)

    async def test_restart_waits_for_end_of_call(self):
        self.modem.inject_call("+491711234567")
        await self.pump()
        self.hw.press("CALL")
        await self.pump()
        self.admin.put_settings({"news_led": False})
        self.q.put_nowait("tick")
        await self.pump()
        self.assertFalse(self.phone.restart_event.is_set())  # nie mitten im Gespräch
        self.modem.inject("call_end")
        await self.pump()
        self.q.put_nowait("tick")
        await self.pump()
        self.assertTrue(await self._until(lambda: self.phone.restart_event.is_set()))

    async def test_volume_is_live(self):
        res = self.admin.put_settings({"volume": 2})
        self.assertFalse(res["restart"])
        self.assertEqual(self.audio.volume, 2)
        self.assertIsNone(self.phone.restart_reason)

    async def test_bad_values_are_rejected_and_file_untouched(self):
        before = self.cfg_path.read_text()
        for change in ({"volume": 9}, {"volume": "laut"}, {"news_led": 1}, {"dock_in_call": "x"},
                       {"hybrid.prefer": "home"}, {"gibt_es_nicht": 1}, {"quiet_hours": [25, 7]},
                       {"owner_name": "a\nb"}):
            with self.assertRaises(ApiError, msg=change) as e:
                self.admin.put_settings(change)
            self.assertEqual(e.exception.status, 400)
        self.assertEqual(self.cfg_path.read_text(), before)

    async def test_contacts_roundtrip_and_validation(self):
        res = self.admin.contacts()
        self.assertEqual(res["contacts"][0]["name"], "Peter")
        new = res["contacts"] + [{"name": "Frau Schmidt", "number": "069 900 09100", "spoken": ["Nachbarin"],
                                  "speed_dial": 5}]
        self.admin.put_contacts(new)
        cfg = config.load(self.cfg_path)
        self.assertEqual(cfg.by_speed_dial(5).number, "06990009100")
        self.assertEqual(cfg.by_speed_dial(5).spoken, ["nachbarin"])
        for bad in ([{"name": "", "number": "0301"}],
                    [{"name": "A", "number": "abc"}],
                    [{"name": "A", "number": "0301", "speed_dial": 1}, {"name": "B", "number": "0302", "speed_dial": 1}],
                    [{"name": "A", "number": "0301", "emergency": 0}],
                    [{"name": "A", "number": "0301", "spoken": ["zwei wörter"]}]):
            with self.assertRaises(ApiError):
                validate_contacts(bad)

    async def test_speak_only_when_idle(self):
        tok = self.token()
        await self.admin.handle("POST", "/api/v1/speak", self.auth(tok), json.dumps({"text": "Hallo Oma"}).encode())
        await self.pump()
        self.assertIn("Hallo Oma", self.audio.spoken)
        self.modem.inject_call("+491711234567")
        await self.pump()
        with self.assertRaises(ApiError) as e:
            await self.admin.handle("POST", "/api/v1/speak", self.auth(tok), b'{"text": "x"}')
        self.assertEqual(e.exception.status, 409)

    async def _until(self, cond, n=200):
        for _ in range(n):
            if cond():
                return True
            await self.pump(1)
        return False


class HybridSettingsTests(AdminBase):
    variant = "hybrid"

    async def test_hybrid_group_present(self):
        titles = [g["title"] for g in self.admin.settings()["groups"]]
        self.assertIn("Hybrid", titles)
        self.admin.put_settings({"hybrid.home_modem": "off"})
        self.assertEqual(config.load(self.cfg_path).hybrid["home_modem"], "off")


class HttpsTests(AdminBase):
    async def test_end_to_end_over_tls(self):
        self.cfg.admin = {"port": 0, "bind": "127.0.0.1"}
        self.admin = AdminServer(self.cfg, self.cfg_path, self.phone, clock=lambda: self.t)
        self.phone.admin = self.admin
        await self.admin.start()
        try:
            base = f"https://127.0.0.1:{self.admin.port}/api/v1"
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE                  # die App pinnt stattdessen den Fingerabdruck

            def call(method, path, body=None, token=None):
                req = urllib.request.Request(base + path, method=method,
                                             data=json.dumps(body).encode() if body is not None else None)
                req.add_header("Content-Type", "application/json")
                if token:
                    req.add_header("Authorization", f"Bearer {token}")
                try:
                    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                        return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())

            loop = asyncio.get_running_loop()
            run = lambda *a, **k: loop.run_in_executor(None, lambda: call(*a, **k))  # noqa: E731
            st, info = await run("GET", "/info")
            self.assertEqual((st, info["app"], info["version"]), (200, "omafon", __version__))
            st, _ = await run("GET", "/status")
            self.assertEqual(st, 401)
            code = self.admin.open_pairing()
            st, res = await run("POST", "/pair", {"code": code, "client_name": "Pixel"})
            self.assertEqual(st, 200)
            st, status = await run("GET", "/status", token=res["token"])
            self.assertEqual((st, status["variant"], status["state"]), (200, "sip", "idle"))
            st, err = await run("PUT", "/settings", {"values": {"volume": 0}}, token=res["token"])
            self.assertEqual(st, 400)
            self.assertIn("Lautstärke", err["error"])
            self.assertEqual(len(self.admin.fingerprint()), 64)
        finally:
            await self.admin.stop()


def make_package(version: str) -> bytes:
    """Release-Paket aus dem aktuellen Code, Version umgeschrieben."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for f in sorted((ROOT / "omafon").glob("*.py")):
            data = f.read_bytes()
            if f.name == "__init__.py":
                data = data.replace(f'"{__version__}"'.encode(), f'"{version}"'.encode())
            info = tarfile.TarInfo(f"omafon/{f.name}")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@unittest.skipUnless(HAVE_CRYPTO, "cryptography fehlt")
class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.key = Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization
        self.pub = base64.b64encode(self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        self.files = {}

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, version, pkg=None, tamper=None):
        pkg = pkg if pkg is not None else make_package(version)
        m = {"version": version, "url": f"https://example.invalid/{version}.tar.gz",
             "sha256": hashlib.sha256(pkg).hexdigest(), "notes": "Test"}
        m["signature"] = base64.b64encode(self.key.sign(canonical(m))).decode()
        if tamper:
            m.update(tamper)
        self.files["https://example.invalid/manifest.json"] = json.dumps(m).encode()
        self.files[m["url"]] = pkg

    def updater(self, version=__version__):
        def opener(url, timeout):
            return io.BytesIO(self.files[url])
        return Updater(self.data, version, "https://example.invalid/manifest.json", self.pub, opener=opener)

    def test_install_boot_confirm(self):
        self.publish("9.9.0")
        up = self.updater()
        info = up.check()
        self.assertTrue(info["update_available"])
        self.assertEqual(info["available"]["version"], "9.9.0")
        self.assertEqual(up.install(), "9.9.0")
        self.assertEqual((self.data / "current").resolve(), (self.data / "releases" / "9.9.0").resolve())
        self.assertEqual(up.state.previous, BASIS)          # Rückfall: Erstinstallation
        new = self.updater("9.9.0")
        self.assertEqual(new.boot(), "9.9.0")
        self.assertEqual(new.state.phase, "idle")           # "restarting" ist nach dem Start vorbei
        new.confirm()
        self.assertEqual(new.load().pending, "")

    def test_failed_boots_roll_back(self):
        self.publish("9.9.0")
        up = self.updater()
        up.check()
        up.install()
        for _ in range(MAX_BOOTS):
            self.assertEqual(self.updater("9.9.0").boot(), "9.9.0")
        self.assertEqual(self.updater("9.9.0").boot(), BASIS)  # 4. Start ohne Bestätigung
        self.assertFalse((self.data / "current").exists())   # Wrapper nimmt /opt/omafon
        state = self.updater().load()
        self.assertIn("nicht stabil", state.last_error)
        self.assertEqual(state.phase, "error")              # App zeigt den Rückfall an

    def test_failed_boots_without_previous_fall_back_to_basis(self):
        self.publish("9.9.0")
        up = self.updater()
        up.check(); up.install()
        up.state.previous = "8.0.0"                          # gibt es nicht (mehr)
        up.save()
        for _ in range(MAX_BOOTS):
            self.updater("9.9.0").boot()
        self.assertEqual(self.updater("9.9.0").boot(), BASIS)
        self.assertFalse((self.data / "current").exists())

    def test_rollback_between_releases(self):
        self.publish("9.9.0")
        up = self.updater()
        up.check(); up.install()
        up2 = self.updater("9.9.0")
        up2.boot(); up2.confirm()
        self.publish("9.9.1")
        up2.check(); up2.install()
        self.assertEqual(up2.state.previous, "9.9.0")
        up3 = self.updater("9.9.1")
        self.assertEqual(up3.rollback(), "9.9.0")
        self.assertEqual((self.data / "current").resolve().name, "9.9.0")

    def test_no_downgrade_and_strict_manifest(self):
        self.publish("0.1.0")                                 # altes, echt signiertes Manifest
        up = self.updater()
        up.check()
        with self.assertRaises(UpdateError) as e:
            up.install()
        self.assertIn("nicht neuer", str(e.exception))
        for bad in ("@basis", "../9.9", "9.9/x", ""):
            m = {"version": bad, "url": "https://example.invalid/p.tar.gz", "sha256": "0" * 64, "notes": ""}
            m["signature"] = base64.b64encode(self.key.sign(canonical(m))).decode()
            self.files["https://example.invalid/manifest.json"] = json.dumps(m).encode()
            with self.assertRaises(UpdateError):
                self.updater().check()

    def test_missing_key_is_a_clean_error(self):
        self.publish("9.9.0")
        up = self.updater()
        up.check()
        up.public_key = None                                  # Schlüssel aus der Konfiguration entfernt
        with self.assertRaises(UpdateError):
            up.install()

    def test_package_size_is_limited(self):
        import omafon.update as upd
        self.publish("9.9.0")
        up = self.updater()
        up.check()
        old, upd.MAX_PACKAGE = upd.MAX_PACKAGE, 100
        try:
            with self.assertRaises(UpdateError) as e:
                up.install()
        finally:
            upd.MAX_PACKAGE = old
        self.assertIn("zu groß", str(e.exception))

    def test_rejects_bad_signature_checksum_and_unsafe_tar(self):
        self.publish("9.9.0", tamper={"version": "9.9.9"})  # Signatur passt nicht mehr
        with self.assertRaises(UpdateError):
            self.updater().check()
        self.publish("9.9.0")
        up = self.updater()
        up.check()
        self.files[up.state.available["url"]] = b"anderer Inhalt"
        with self.assertRaises(UpdateError):
            up.install()
        bad = io.BytesIO()
        with tarfile.open(fileobj=bad, mode="w:gz") as t:
            info = tarfile.TarInfo("../boese.py")
            info.size = 1
            t.addfile(info, io.BytesIO(b"x"))
        self.publish("9.9.2", pkg=bad.getvalue())
        up = self.updater()
        up.check()
        with self.assertRaises(UpdateError):
            up.install()
        self.assertFalse((self.data.parent / "boese.py").exists())

    def test_broken_package_fails_smoke_test(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            for name, data in (("omafon/__init__.py", b"__version__ = '9.9.3'\n"),
                               ("omafon/phone.py", b"raise RuntimeError('kaputt')\n")):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
        self.publish("9.9.3", pkg=buf.getvalue())
        up = self.updater()
        up.check()
        with self.assertRaises(UpdateError) as e:
            up.install()
        self.assertIn("startet nicht", str(e.exception))
        self.assertFalse((self.data / "current").exists())

    def test_not_configured(self):
        with self.assertRaises(UpdateError):
            Updater(self.data, __version__).check()


class RobustApiTests(AdminBase):
    """Gefunden mit einem HTTP-Fuzzer: nie 500, immer eine verständliche 400."""

    async def test_odd_json_is_rejected_cleanly(self):
        tok = self.token()
        for path, body in (("/api/v1/speak", b"null"), ("/api/v1/settings", b"[]"),
                           ("/api/v1/settings", b'{"values": {"volume": 1e999}}'),
                           ("/api/v1/settings", b'{"values": {"speech_rate": NaN}}'),
                           ("/api/v1/settings", b'{"values": {"volume": ' + b"9" * 500 + b"}}"),
                           ("/api/v1/contacts", b'"x"'), ("/api/v1/settings", b"\xff\xfe")):
            method = "POST" if path.endswith("speak") else "PUT"
            with self.subTest(body=body[:40]), self.assertRaises(ApiError) as e:
                await self.admin.handle(method, path, self.auth(tok), body)
            self.assertEqual(e.exception.status, 400)
        config.load(self.cfg_path)                                 # Datei unversehrt


class LocalOnlyTests(unittest.TestCase):
    def test_only_home_network_addresses(self):
        from omafon.admin import local_peer
        for ip in ("192.168.178.20", "10.0.0.5", "172.16.1.1", "127.0.0.1", "fe80::1%wlan0",
                   "fd00::5", "::ffff:192.168.1.9", "10.8.0.2"):
            self.assertTrue(local_peer(ip), ip)
        for ip in ("8.8.8.8", "2a00:1450::1", "::ffff:8.8.8.8", "", "quatsch"):
            self.assertFalse(local_peer(ip), ip)
        self.assertTrue(local_peer("8.8.8.8", allow_public=True))


class UpdateApiTests(AdminBase):
    async def test_check_refused_while_installing(self):
        up = Updater(self.cfg.data_dir, __version__)
        self.admin.updater = up
        up.state.phase = "downloading"
        tok = self.token()
        for path in ("/api/v1/update/check", "/api/v1/update/rollback"):
            with self.assertRaises(ApiError) as e:
                await self.admin.handle("POST", path, self.auth(tok), b"")
            self.assertEqual(e.exception.status, 409)
        self.assertEqual(up.state.phase, "downloading")          # Fortschritt nicht überschrieben

    async def test_yaml_on_off_shown_as_choice(self):
        raw = self.cfg_path.read_text(encoding="utf-8")
        self.cfg_path.write_text(raw + "\nhybrid:\n  home_modem: off\n", encoding="utf-8")
        self.cfg.backend = "hybrid"
        text = self.cfg_path.read_text(encoding="utf-8").replace("backend: sip", "backend: hybrid")
        self.cfg_path.write_text(text, encoding="utf-8")
        items = {i["key"]: i for g in self.admin.settings()["groups"] for i in g["items"]}
        self.assertEqual(items["hybrid.home_modem"]["value"], "off")


class SavedConfigTests(unittest.TestCase):
    """Auf dem Pi ist /etc schreibgeschützt: App-Änderungen liegen in /data."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.seed = d / "etc.yaml"
        text = (ROOT / "config.festnetz.example.yaml").read_text(encoding="utf-8")
        self.seed.write_text(text.replace("data_dir: /data/omafon", f"data_dir: {d / 'data'}"), encoding="utf-8")
        self.saved = d / "data" / "config.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_copied_then_saved_copy_wins(self):
        from omafon.main import use_saved_config
        path, cfg = use_saved_config(str(self.seed), config.load(self.seed))
        self.assertEqual(Path(path), self.saved)              # Vorlage nach /data kopiert
        self.saved.write_text(self.saved.read_text(encoding="utf-8").replace(
            "hangup_hold_s: 0.5", "hangup_hold_s: 0.9"), encoding="utf-8")
        path, cfg = use_saved_config(str(self.seed), config.load(self.seed))
        self.assertEqual(cfg.hangup_hold_s, 0.9)

    def test_broken_saved_copy_falls_back_to_seed(self):
        from omafon.main import use_saved_config
        self.saved.parent.mkdir(parents=True)
        self.saved.write_text("volume: [kaputt", encoding="utf-8")
        with self.assertLogs("omafon", "ERROR"):
            path, cfg = use_saved_config(str(self.seed), config.load(self.seed))
        self.assertEqual(Path(path), self.seed)


class ApiFixtureTests(AdminBase):
    """Die JSON-Beispiele der Android-App müssen zur Schnittstelle passen."""

    async def test_fixtures_up_to_date(self):
        from tools.api_fixtures import fixtures
        fx = fixtures()
        d = ROOT / "android" / "app" / "src" / "test" / "resources" / "api"
        for name, data in fx.items():
            path = d / name
            self.assertTrue(path.exists(), f"{path} fehlt – python3 -m tools.api_fixtures ausführen")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data,
                             f"{name} veraltet – python3 -m tools.api_fixtures ausführen")


if __name__ == "__main__":
    unittest.main()
