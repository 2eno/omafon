# Omafon-App (Android)

Mit der App verwalten Angehörige das Omafon vom Handy aus: Einstellungen,
Kontakte und Notrufkette, Updates, Testansage. Sie läuft **nur im selben WLAN**
wie das Omafon – das Telefon ist aus dem Internet nicht erreichbar.

Quellcode: [`android/`](../android) (Kotlin, Jetpack Compose, Material 3).
Die CI baut bei jedem Push eine Debug-APK (Artefakt `omafon-app-debug`).

## Bildschirme

| Bildschirm | Inhalt |
|---|---|
| Geräte | gekoppelte Omafone; per mDNS im WLAN gefundene; Adresse von Hand eingeben |
| Koppeln | Anleitung, Code-Eingabe, Kurzform des Zertifikats |
| Übersicht | Akku, Verbindung, ungelesene Nachrichten, verpasste Anrufe, Zustand; Testansage; Neustart |
| Einstellungen | alle Werte, die das Omafon anbietet, nach Gruppen; Speichern mit Neustart in Ruhe |
| Kontakte | Name, Nummer, Sprachwahl-Wörter, Kurzwahl 1–9, Platz in der Notrufkette, E-Mail/Telegram |
| Updates | installierte und verfügbare Version, Installieren mit Fortschritt, Zurück zur alten Version |
| Gekoppelte Apps | wer verwalten darf; einzelne Handys entkoppeln |

Die Einstellungen beschreibt das Omafon selbst (Schema in `omafon/admin.py`,
`SETTINGS`). Neue Einstellungen erscheinen in der App ohne App-Update.

## Koppeln

1. Handy ins WLAN des Omafon. Die App findet es (`_omafon._tcp`, Avahi), sonst
   die IP-Adresse aus der Fritz!Box eingeben (Port 8443).
2. Am Omafon die **Raute-Taste lang drücken**. Es sagt „Kopplungscode für die
   Omafon-App“ und sechs Ziffern, zweimal.
3. Code in der App eingeben. Er gilt 5 Minuten, nach 5 falschen Versuchen ist
   das Koppeln gesperrt, bis erneut Raute lang gedrückt wird.
4. Das Omafon sagt „Die App ist jetzt verbunden.“

## Sicherheit

- **HTTPS** mit selbst signiertem Zertifikat (EC P-256, beim ersten Start mit
  `openssl` erzeugt, `/data/omafon/admin/`). Die App merkt sich beim Koppeln den
  SHA-256-Fingerabdruck und lehnt danach jedes andere Zertifikat ab
  („Zertifikat hat sich geändert“ → neu koppeln). Wer beim allerersten Kontakt
  im selben WLAN mithört *und* sich dazwischenschaltet, könnte das umgehen
  (Trust on first use) – im eigenen Heimnetz ein vertretbares Restrisiko.
- **Token** je Handy, auf dem Omafon nur als SHA-256 gespeichert, in der App mit
  einem Schlüssel aus dem Android-Keystore verschlüsselt und von Sicherungen
  ausgenommen. Verlorenes Handy: in der App unter „Gekoppelte Apps“ entkoppeln.
- **Kennwörter** (SIP, Fritz!Box, SMTP, Telegram) schickt das Omafon nie an die
  App, nur „gesetzt ja/nein“. Neue Kennwörter lassen sich setzen.
- **Kein Zugriff aus dem Internet.** Kein Port in der Fritz!Box freigeben. Für
  Fernwartung: Fritz!Box-VPN (WireGuard) aufs Handy, dann wie zu Hause.
- Der **Update-Schlüssel** (`update_public_key`) ist absichtlich nicht über die
  App änderbar – sonst könnte, wer die App hat, beliebigen Code einspielen.

## Was passiert beim Speichern?

Das Omafon prüft die Werte (Grenzen, Typen, Kontakte wie beim Start), schreibt
`/data/omafon/config.yaml` atomar (alte Fassung `config.yaml.bak`) und startet
neu, **sobald es in Ruhe ist** – nie mitten im Gespräch, Notruf oder Diktat.
Vorher sagt es „Neue Einstellungen. Das Telefon startet kurz neu.“ Nur die
Lautstärke wirkt sofort.

`/etc/omafon/config.yaml` ist danach nur noch die Vorlage: Gibt es
`/data/omafon/config.yaml`, gilt diese. Ist sie beschädigt, startet das Omafon
mit der Vorlage.

## Updates

```
App            Omafon                                  Webserver
 │ Suchen ───▶ lädt manifest.json ◀───────────────────── manifest.json
 │             prüft Ed25519-Signatur                  omafon-X.tar.gz
 │ Install ──▶ lädt Paket, prüft SHA-256, entpackt sicher,
 │             Importtest, /data/omafon/releases/X
 │             current → releases/X, wartet auf Ruhe, Neustart
 │             läuft X 2 Minuten stabil → bestätigt
 │             3 Fehlstarts → automatisch zurück
```

- Pakete enthalten nur `omafon/*.py`. Stimmen, Modelle, Konfiguration bleiben.
- Das System unter `/opt/omafon` bleibt unverändert; der Start-Wrapper
  (`systemd/omafon-start.sh`) läuft immer von dort und kann so auch nach einem
  kaputten Update zurückschalten.
- „Zurück zur vorherigen Version“ in der App geht jederzeit, solange die
  vorherige Version noch da ist.

### Update-Kanal einrichten (einmalig, am PC)

```bash
pip install cryptography
python3 -m tools.make_release keygen ~/omafon-signing     # privaten Schlüssel sicher aufbewahren!
# Ausgabe update_public_key in /etc/omafon/config.yaml (bzw. /data/omafon/config.yaml) eintragen
```

Für jedes Release `__version__` in `omafon/__init__.py` erhöhen, dann:

```bash
python3 -m tools.make_release build --key ~/omafon-signing/omafon_update.key \
    --base-url https://updates.example.org/omafon/ --notes "Was ist neu" --out dist/
```

`dist/manifest.json` und das Paket auf einen HTTPS-Webserver legen und in der
App unter Einstellungen → Updates die URL von `manifest.json` eintragen.

## Installation auf dem Omafon

Zusätzlich zur Installation im README:

```bash
sudo apt install python3-cryptography avahi-daemon openssl
sudo cp systemd/omafon.avahi.xml /etc/avahi/services/omafon.service
sudo install -d -o omafon -g omafon -m 700 /data/omafon
```

`systemd/omafon.service` startet über `systemd/omafon-start.sh`.

## App bauen

```bash
cd android
./gradlew testDebugUnitTest      # Tests (JSON-Beispiele vom Omafon, TLS-Pinning, Regeln)
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
```

Braucht JDK 17+ und das Android-SDK (`ANDROID_HOME` oder `local.properties`).
Ändert sich die Schnittstelle, `python3 -m tools.api_fixtures` laufen lassen –
das erneuert die JSON-Beispiele unter `android/app/src/test/resources/api/`, und
`tests/test_admin.py` schlägt fehl, solange sie veraltet sind.

## Offen

- Release-Signatur der APK (eigener Keystore) und Verteilung (F-Droid/direkt).
- Bedienung am echten Gerät und mit TalkBack noch nicht erprobt – getestet sind
  Bau, Lint und die Unit-Tests.
- Abhängigkeiten sind bewusst auf erprobte Versionen gepinnt (AGP 8.7, Compose
  BOM 2024.12); ein Sprung auf AGP 9 ist ein eigener Schritt.
