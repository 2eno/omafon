# Festnetz-Variante: Recherche und Bewertung

*[English](festnetz-recherche.md) · Deutsch*

Stand: November 2026. Ziel: ein schnurloses Omafon mit Ladeschale, das sich an der
Fritz!Box anmeldet. Gleiche Zielgruppe wie die Mobilfunk-Variante: fortgeschrittene
AMD, fast blind, Bedienung ohne Display, alles per Sprachausgabe.

Belege stehen in eckigen Klammern und verweisen auf die [Quellen](#quellen) am Ende.
**Ungeprüft** heißt: nur Forenaussage oder eigener Schluss, vor dem Bau am echten
Gerät prüfen.

## Kurzfassung

- **Empfehlung: IP-Telefon über WLAN (SIP) mit dem Raspberry Pi Zero 2 W.** Die
  Software dafür liegt in diesem Branch (`backend: sip`). Deine Vorannahme stimmt.
- **Ein eigenes DECT-Handteil ist nicht unmöglich, aber unverhältnismäßig.** Es gibt
  ein vorzertifiziertes GAP-Modul (Dialog/Renesas SC14CVMDECT) [8–10]. Mit eigener
  Firmware muss das Endgerät aber neu zertifiziert werden [8], die Unterlagen sind
  alt (2011–2015), und ob es noch lieferbar ist, ist offen.
- **Widerspruch in einem Punkt:** DECT würde das größte Problem der WLAN-Lösung, die
  **Akkulaufzeit**, *nicht* lösen. Sprachausgabe (Piper), Tasten und Spracherkennung
  laufen auch dann auf dem Pi, und der Pi braucht in Ruhe etwa 0,6 W [13]. Der Pi ist
  der Hauptverbraucher, nicht das Funkteil.
- **Auch „kleinerer Akku“ stimmt nur halb.** Ohne Modem entfallen die 2-A-Sendespitzen.
  Akku und Spannungswandler dürfen also schwächer belastbar sein. Der Ruhestrom sinkt
  aber kaum (Modem in Ruhe ca. 0,1 W, Pi ca. 0,6 W, siehe
  [festnetz-hardware.md](festnetz-hardware.md)). Mit gleich großem Akku hält die
  Festnetz-Variante etwas länger; ein kleinerer Akku verkürzt die Bereitschaft.
- Wichtiger Vorteil Festnetz: Beim Notruf 112 über den Festnetzanschluss übermittelt
  der Anbieter in der Regel die Anschlussadresse. GPS wird damit weniger wichtig
  (ungeprüft für den konkreten Anschluss, siehe offene Fragen).

## 1. Wie Telefone sich an der Fritz!Box anmelden

### DECT-Handteil

- Die Fritz!Box ist eine DECT-Basis mit dem Profil **GAP**. Damit funktionieren
  Handteile verschiedener Hersteller zusammen; welche Zusatzfunktionen gehen, hängt
  vom Hersteller ab [5, 6].
- Mit Fremdgeräten gibt es oft nur Grundfunktionen. Laut Forenberichten gehört nicht
  einmal die Rufnummernanzeige (CLIP) sicher zu GAP, Telefonbuchzugriff schon gar
  nicht [6]. Manche GAP-Geräte lassen sich an bestimmten Modellen nicht anmelden [6].
- Für nicht GAP-konforme Geräte bietet die Fritz!Box eine Problemlösungs-Option in den
  DECT-Einstellungen [7]. Eine Garantie gibt AVM nur bei GAP [7].
- **DECT NR+ (DECT-2020)** ist ein Datenfunkstandard für IoT, kein Sprach-Handteil-
  Profil, und hilft hier nicht [7].

### IP-Telefon (SIP) über LAN/WLAN

- Fritz!Box: *Telefonie → Telefoniegeräte → Neues Gerät → Telefon → LAN/WLAN
  (IP-Telefon)*. Die Box vergibt Benutzername und Kennwort, die das Telefon zur
  Registrierung nutzt. Registrar ist die Fritz!Box selbst [1, 2].
- Keinen STUN-Server eintragen. Das Telefon muss im Heimnetz sein, **nicht im
  Gastnetz** [1, 2].
- IP-Telefone dürfen nach dem Einrichten zunächst nur **Inlandsgespräche und
  Notrufnummern** wählen. Auslandsgespräche lassen sich freischalten [3].
- Für die Anmeldung aus dem Internet muss der Benutzername mindestens 8 Zeichen
  haben [1]. Das brauchen wir nicht, die Option bleibt aus.
- Der Raspberry Pi Zero 2 W kann nur **2,4-GHz-WLAN**. Das 2,4-GHz-Band der
  Fritz!Box muss also an sein.

## 2. TR-064: Telefonbuch, Anrufliste, Anrufbeantworter

AVM dokumentiert TR-064 offiziell (Dienste X_AVM-DE_OnTel, X_AVM-DE_TAM u. a.) [4].

| Zweck | Dienst / Aktion | Ergebnis |
|---|---|---|
| Telefonbuch | `X_AVM-DE_OnTel:1` `GetPhonebook(NewPhonebookID)` | URL zu einer XML-Datei mit `contact/person/realName` und `telephony/number` [4, 11] |
| Anrufliste | `X_AVM-DE_OnTel:1` `GetCallList` | URL zu einer XML-Liste; Fehler 820, wenn nicht unterstützt [11] |
| AB-Nachrichten | `X_AVM-DE_TAM:1` `GetMessageList(NewIndex)` | URL zu einer XML-Liste; je Nachricht `Index`, `Tam`, `Number`, `Name`, `Date`, `Duration`, `New`, `Path` [12, 14] |
| AB gehört markieren | `X_AVM-DE_TAM:1` `MarkMessage` | – [12] |
| AB löschen | `X_AVM-DE_TAM:1` `DeleteMessage` | – [12] |

- **Aufnahmen herunterladen:** `Path` zeigt auf
  `/download.lua?path=/data/tam/rec/rec.0.NNN` [14]. Für den Download braucht es die
  Sitzungs-ID (`sid`). Sie steckt in der URL, die `GetMessageList` liefert. Das ist
  ein Schluss aus dem Aufbau dieser URLs, nicht offiziell belegt.
- **Format der Aufnahmen: offen.** Der Push-Service verschickt AB-Nachrichten als
  WAV [15]. Die Dateien auf der Box sollen laut einem Forenbeitrag ein anderes Format
  haben (genannt wird Speex, unbestätigt) [15]. Omafon spielt WAV direkt ab und
  wandelt alles andere mit `ffmpeg`. Klappt beides nicht, sagt das Telefon
  „Abspielen geht leider nicht“.
- **Zugang:** eigener Fritz!Box-Benutzer, nur mit dem Recht „Sprachnachrichten,
  Faxnachrichten, FRITZ!App Fon und Anrufliste“. TR-064 muss unter *Heimnetz →
  Netzwerk → Netzwerkeinstellungen* erlaubt sein.
- **Bibliothek:** `fritzconnection` (Python, in Debian als `python3-fritzconnection`)
  übernimmt SOAP und Anmeldung [16, 17]. Die Namen der Dienste prüft man auf der
  eigenen Box mit `fritzconnection -a fritz.box -s` [17]. Bei manchen Modellen
  heißen sie anders [17].
- **Alternative für Anrufereignisse:** der Callmonitor auf TCP-Port 1012
  (einschalten mit `#96*5*`) liefert `RING/CALL/CONNECT/DISCONNECT` [18]. Wir
  brauchen ihn nicht, weil baresip die Anrufe selbst meldet.

## 3. DECT-Module für Eigenbauten

| Modul | Was es ist | Zulassung | Bewertung |
|---|---|---|---|
| Dialog/Renesas **SC14CVMDECT** („Cordless Voice Module“) | Funk und Basisband, GAP-Protokollstapel, Steuerung per Host-Schnittstelle [8, 9] | EU-DECT (ETSI), FCC, J-DECT vorzertifiziert [8]. Laut Hersteller nur für Handteile [8]. **Mit anderer als der Standard-Software muss das Endgerät neu zertifiziert werden** [8] | Einziges halbwegs offen dokumentiertes Modul. Unterlagen 2011–2015, Liefersituation unklar [10] |
| DECT-ULE-Module | Datenfunk für Sensoren | – | keine Sprach-Handteile |
| DECT NR+ (z. B. Nordic nRF91-Serie) | DECT-2020, Datenfunk | – | nicht GAP-kompatibel, keine Sprache zur Fritz!Box [7] |

**Ergebnis:** Es gibt zugelassene Module, aber keine Bastler-taugliche Kette aus
Modul, Entwicklungsboard und Doku, die heute sicher lieferbar ist. Dazu kommen
HF-Layout, Antenne und die Frage der Konformität des Endgeräts.

## 4. Zulassung (Funkanlagengesetz / RED)

- Das FuAG regelt das **Bereitstellen auf dem Markt „im Rahmen einer
  Geschäftstätigkeit“** und das Inverkehrbringen. Die Pflichten (Konformitäts-
  erklärung, CE, technische Unterlagen) treffen den Hersteller [19].
- Ob ein **rein privater Einzelbau** ohne Weitergabe darunter fällt, geben die
  Gesetzestexte nicht eindeutig her [19]. **Offene Frage** (BNetzA oder
  Fachanwalt).
- **WLAN-Weg:** Das Funkmodul des Pi Zero 2 W bleibt unverändert mit seiner
  Platinenantenne. Der bekannte Umbau auf eine externe Antenne (U.FL) **hebt die
  Funkzulassung auf** [20]. Deshalb keine externe Antenne. Ist die WLAN-Abdeckung
  schwach, hilft ein Fritz!Repeater.
- **DECT-Weg:** eigene Firmware auf dem Modul bedeutet Neuzertifizierung [8]. Auch
  ein privater Weiterverkauf oder eine Weitergabe machte einen zum Hersteller [19].

## 5. Andere Wege, ehrlich genannt

- **Fertiges Senioren-DECT-Telefon an der Fritz!Box:** Händler beschreiben z. B. das
  Gigaset E560A mit „sprechenden Tasten“ und SOS-Taste [21]. Die eigene Basis hängt
  **analog** an der Fritz!Box (FON-Anschluss), dann gehen alle Funktionen des
  Herstellers [22]. Die Sprachansage der Tasten habe ich in einer Herstellerquelle
  nicht bestätigt gefunden. Ansage von Namen, Uhrzeit und AB-Nachrichten,
  Sprachwahl und Notrufkette fehlen.
  *Gut als Vergleich und als Notfall-Ersatzgerät, nicht als Ersatz für Omafon.*
- **Fritz!App Fon auf einem Smartphone** mit Bildschirmleser: günstig, aber für
  fast Blinde ohne Smartphone-Erfahrung zu komplex.
- **Pi plus Bluetooth zu einem DECT-Handteil:** Bluetooth gibt es nur bei wenigen
  Modellen, oft eingeschränkt [6]. Zwei Geräte, zwei Akkus, mehr Fehlerquellen.

## 6. Bewertung

| | **A: WLAN-SIP mit Pi Zero 2 W** (empfohlen) | **B: Eigenbau-DECT-Handteil** | *Vergleich: fertiges Senioren-DECT* |
|---|---|---|---|
| **Aufwand** | Mittel. Software steht (baresip, TR-064, Simulator, Tests). Hardware = Mobilfunk-Variante ohne Modem plus Ladeschale | Sehr hoch. Modulbeschaffung (B2B), Host-Protokoll, HF-Layout, Antenne; Pi trotzdem nötig | Keiner |
| **Zulassung** | Unkritisch, solange das Pi-Funkmodul unverändert bleibt (keine externe Antenne) [20] | Neuzertifizierung bei eigener Firmware [8]; offen für Einzelbau [19] | CE vorhanden |
| **Audioqualität** | Gut. Codecs G.722 (HD) und G.711. Hängt an der WLAN-Qualität; ab ca. −67 dBm stabil, darunter Aussetzer möglich (Erfahrungswert, ungeprüft) | DECT ist sehr robust gegen Störungen; HD nur mit CAT-iq, mit GAP-Fremdgerät unsicher [6] | Gut, Verstärkerfunktion für Hörgeschädigte |
| **Akkulaufzeit** | Schwachpunkt: ca. 14–19 h Bereitschaft mit 3000 mAh (Rechnung in festnetz-hardware.md); muss täglich in die Schale | Funkteil sparsam, aber der Pi frisst dieselbe Energie, also **kaum besser als A** | Tage |
| **Kosten (Material)** | ca. 150–190 € | Modul plus Entwicklungsboard unklar (vermutlich deutlich teurer), dazu der Rest von A | ca. 50–90 € |
| **Funktionen für AMD** | Alles aus Omafon: Ziffern-, Namens- und Uhrzeitansage, AB vorlesen, Sprachwahl, Notrufkette | wie A | Tastenansage (laut Händler), SOS-Taste |

### Empfehlung

**Weg A.** Er nutzt die vorhandene Software fast unverändert, braucht keine eigene
Funkzulassung und kostet weniger als die Mobilfunk-Variante. Den Akkunachteil
fängt die Ladeschale auf. Das Telefon „wohnt“ dort, nimmt Anrufe beim Abheben an
und legt beim Einstellen auf. Ein fertiges Senioren-DECT-Telefon an einem zweiten
FON-Anschluss der Fritz!Box ist ein sinnvolles **Ersatzgerät**, falls Omafon
ausfällt.

## 7. Was in der Fritz!Box einzurichten ist

1. *Telefonie → Telefoniegeräte → Neues Gerät → Telefon → LAN/WLAN (IP-Telefon)*,
   Name „Omafon“. Benutzername und Kennwort in `config.yaml` unter `sip:` eintragen.
2. Ausgehende Rufnummer und die Rufnummern festlegen, auf die Omafon klingeln soll.
3. *System → FRITZ!Box-Benutzer*: Benutzer „omafon“ nur mit dem Recht
   „Sprachnachrichten, Faxnachrichten, FRITZ!App Fon und Anrufliste“, in
   `config.yaml` unter `fritz:` eintragen.
4. *Heimnetz → Netzwerk → Netzwerkeinstellungen*: „Zugriff für Anwendungen zulassen“
   (TR-064) an.
5. Anrufbeantworter einschalten. Ansagezeit so lang, dass Oma rechtzeitig am
   Telefon ist (z. B. 30 s).
6. *Telefonie → Wählregeln*: prüfen, dass 110 und 112 über das Festnetz gehen
   [3, 23]. Laut Foren ist das voreingestellt, aber keine Garantie [23].
7. WLAN 2,4 GHz an. Omafon nicht ins Gastnetz.

## Offene Fragen (auch im Pull Request)

1. **Fritz!Box-Modell und FRITZ!OS-Version?** Dienstnamen bei TR-064 und das
   AB-Format können abweichen. Mit `fritzconnection -a fritz.box -s` auf dem Pi prüfen.
2. **Format der AB-Aufnahmen** über `download.lua` (WAV oder anderes)? Erste
   Nachricht herunterladen und mit `file` ansehen.
3. **Notruf über das IP-Telefon:** Geht 112 wirklich über die Festnetzleitung, und
   übermittelt der Anbieter die Adresse? Beim Anbieter nachfragen, Wählregel prüfen.
   Nicht testweise 112 wählen.
4. **Rechtslage Einzelbau** (FuAG/RED) für ein privat genutztes Gerät mit
   unverändertem Pi-Funkmodul.
5. **Freisprechen in der Schale** braucht Echounterdrückung. baresip hat dafür
   Module (z. B. WebRTC-AEC); am echten Gerät prüfen.
6. **baresip-Details:** Ob `stopringing` den baresip-eigenen Klingelton zuverlässig
   stoppt und `netroam` nach einem WLAN-Wechsel neu registriert, lässt sich erst
   am Pi prüfen.

## Quellen

1. AVM-Hilfe: Connecting an IP Telephone to the FRITZ!Box (7590) – https://service.avm.de/help/en/FRITZ-Box-7590/019/hilfe_fon_howto_ip-telefon
2. IP-Telefon an FRITZ!Box anmelden (Anleitung, PDF) – https://www.mikrocontroller.net/attachment/73061/IP-Telefon_an_FRITZ_Box_anmelden.PDF
3. AVM-Hilfe 7590 (IP-Telefone nur Inland und Notruf ab Werk) – https://service.avm.de/help/en/FRITZ-Box-7590/015/hilfe_fon_howto_ip-telefon
4. AVM/FRITZ! Schnittstellen für Entwickler (TR-064, X_AVM-DE_OnTel, X_AVM-DE_TAM) – https://fritz.com/en/pages/interfaces
5. FRITZ! Knowledge Base: Funktionen mit Schnurlostelefonen (GAP) – https://fritz.com/en/apps/knowledge-base/FRITZ-Box-4690/40_Functions-and-features-that-can-be-used-with-cordless-phones
6. ip-phone-forum.de: Gigaset E720 an Fritz!Box 7490 / Fremd-DECT – https://www.ip-phone-forum.de/threads/gigaset-e720-%C3%BCber-dect-an-fritz-box-7490.326322/ und https://www.ip-phone-forum.de/showthread.php?p=909633
7. Wikipedia: DECT (DECT-2020 NR) – https://en.wikipedia.org/wiki/DECT ; FRITZ! Knowledge Base: GAP-Problemlösung – https://uk.fritz.com/service/knowledge-base/dok/FRITZ-Box-5490/40_Functions-and-features-that-can-be-used-with-cordless-phones/
8. Dialog Semiconductor: SC14CVMDECT SF Datasheet Rev. 3.0 (2015) – https://www.mouser.com/ds/2/713/sc14cvmdect_sf_datasheet_3.0_final_0-908537.pdf
9. FCC ID Y82-SC14S, User Manual CVMDECT – https://fccid.io/Y82-SC14S/User-Manual/user-manual-CVMDECT-2324864
10. Avnet Silica: Renesas Cordless Voice Module SC14CVMDECT (2018) – https://my.avnet.com/silica/products/new-products/npi/2018/dialog-smartbond-cvm/
11. avmtools Wiki: Get-AvmOnTelCallList – https://github.com/chikenborgir/avmtools/wiki/Get-AvmOnTelCallList
12. avmtools: TAM.ps1 (X_AVM-DE_TAM-Aktionen) – https://powershellgallery.com/packages/avmtools/3.148.44/Content/Functions/Generic/TAM.ps1
13. CNX Software: Raspberry Pi Zero 2 W power consumption – https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/
14. ioBroker-Forum: TR-064 Fritzbox Anrufbeantworter (Path rec.0.NNN) – https://forum.iobroker.net/topic/14288/tr-064-fritzbox-anrufbeantworter/20
15. ip-phone-forum.de: Sprachnachrichten von der Box laden / Encoder – https://www.ip-phone-forum.de/threads/sprachnachrichten-von-der-box-laden.191564/ und https://www.ip-phone-forum.de/threads/fritz-box-anrufbeantworter-encoder-decoder.156186/
16. Debian-Paket python3-fritzconnection – https://packages.debian.org/de/sid/all/python3-fritzconnection
17. fritzconnection (GitHub, Doku) – https://github.com/kbr/fritzconnection ; MagicMirror-Forum (Dienstname je Modell) – https://forum.magicmirror.builders/post/12782
18. fritzconnection: Call Monitoring – https://fritzconnection.readthedocs.io/en/1.9.1/sources/call_monitoring.html
19. Funkanlagengesetz (FuAG) – https://www.gesetze-im-internet.de/fuag/__7.html ; IHK Nürnberg Merkblatt Funkanlagen 2023 – https://www.ihk-nuernberg.de/fileadmin/IHK_Nuernberg/Innovation-Technologie-Forschung/Dokumente/2023_MB_Funkanlagen_final.pdf
20. Brian Dorey: Raspberry Pi Zero 2 W external antenna mod – https://www.briandorey.com/post/raspberry-pi-zero-2-w-external-antenna-mod ; Hinweis Zertifizierung: https://www.briandorey.com/post/raspberry-pi-zero-w-external-antenna-mod
21. Händlerangaben Gigaset E560A (sprechende Tasten, SOS) – https://www.homeandsmart.de/dect-schnurlos-telefon-test-vergleich
22. Gigaset E560A Bedienungsanleitung (SOS-Taste an der Basis, analoger Anschluss) – https://gse.gigaset.com/fileadmin/legacy-assets/CustomerCare/Manuals/E5x/E560A/A31008-M2745-B101-1-19_de_DE-LU.pdf
23. ip-phone-forum.de: Notrufnummern in den Wählregeln – https://www.ip-phone-forum.de/threads/notrufnummern-aus-wahlregeln-entfernen.108934/latest ; o2 Community: Notruf 110/112 nicht möglich (7590) – https://hilfe.o2online.de/dsl-kabel-glasfaser-router-software-internet-telefonie-34/notruf-110-und-112-nicht-moeglich-486280
24. baresip Quellcode: ctrl_tcp, menu (dial/accept/hangup/sndcode), Ereignisnamen – https://github.com/baresip/baresip/blob/main/modules/ctrl_tcp/ctrl_tcp.c , https://github.com/baresip/baresip/blob/main/modules/menu/static_menu.c , https://github.com/baresip/baresip/blob/main/src/bevent.c
