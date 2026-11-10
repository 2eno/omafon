# Landline variant: research and assessment

*English · [Deutsch](festnetz-recherche.de.md)*

As of November 2026. Goal: a cordless Omafon with a cradle that registers with the
Fritz!Box. Same target group as the mobile variant: advanced AMD (macular
degeneration), almost blind, operation without a display, everything via speech output.

References are in square brackets and point to the [sources](#sources) at the end.
**Unverified** means: only a forum statement or my own conclusion – check on the real
device before building.

## Summary

- **Recommendation: an IP phone over Wi-Fi (SIP) with the Raspberry Pi Zero 2 W.** The
  software for it is in this branch (`backend: sip`). Your assumption is right.
- **A DECT handset of our own is not impossible, but disproportionate.** There is a
  pre-certified GAP module (Dialog/Renesas SC14CVMDECT) [8–10]. With custom firmware,
  however, the end device has to be re-certified [8], the documents are old
  (2011–2015), and whether it is still available is open.
- **Disagreement on one point:** DECT would *not* solve the biggest problem of the
  Wi-Fi solution, the **battery life**. Speech output (Piper), keys and speech
  recognition still run on the Pi, and the Pi needs about 0.6 W at rest [13]. The Pi is
  the main consumer, not the radio part.
- **“Smaller battery” is only half right too.** Without a modem, the 2 A transmit peaks
  are gone. So battery and voltage converter may be rated lower. But the idle current
  hardly drops (modem at rest approx. 0.1 W, Pi approx. 0.6 W, see
  [festnetz-hardware.md](festnetz-hardware.md)). With an equally large battery the
  landline variant lasts a little longer; a smaller battery shortens the standby time.
- Important advantage of the landline: for an emergency call to 112 over the landline,
  the provider usually transmits the line address. GPS becomes less important
  (unverified for the specific line, see open questions).

## 1. How phones register with the Fritz!Box

### DECT handset

- The Fritz!Box is a DECT base with the **GAP** profile. With it, handsets from
  different manufacturers work together; which extra functions work depends on the
  manufacturer [5, 6].
- Third-party devices often only get basic functions. According to forum reports, not
  even caller ID (CLIP) is reliably part of GAP, let alone phone book access [6]. Some
  GAP devices can’t be registered with certain models [6].
- For devices that are not GAP-compliant, the Fritz!Box offers a troubleshooting option
  in the DECT settings [7]. AVM only gives a guarantee for GAP [7].
- **DECT NR+ (DECT-2020)** is a data radio standard for IoT, not a voice handset
  profile, and doesn’t help here [7].

### IP phone (SIP) over LAN/Wi-Fi

- Fritz!Box: *Telephony → Telephony Devices → New Device → Telephone → LAN/WLAN
  (IP phone)*. The box assigns a user name and password that the phone uses to
  register. The registrar is the Fritz!Box itself [1, 2].
- Don’t enter a STUN server. The phone must be in the home network, **not in the guest
  network** [1, 2].
- After setup, IP phones may initially only dial **domestic calls and emergency
  numbers**. International calls can be enabled [3].
- For registration from the internet, the user name must have at least 8 characters
  [1]. We don’t need that; the option stays off.
- The Raspberry Pi Zero 2 W only supports **2.4 GHz Wi-Fi**. So the Fritz!Box’s
  2.4 GHz band must be on.

## 2. TR-064: phone book, call list, answering machine

AVM documents TR-064 officially (services X_AVM-DE_OnTel, X_AVM-DE_TAM and others) [4].

| Purpose | Service / action | Result |
|---|---|---|
| Phone book | `X_AVM-DE_OnTel:1` `GetPhonebook(NewPhonebookID)` | URL of an XML file with `contact/person/realName` and `telephony/number` [4, 11] |
| Call list | `X_AVM-DE_OnTel:1` `GetCallList` | URL of an XML list; error 820 if not supported [11] |
| Answering machine messages | `X_AVM-DE_TAM:1` `GetMessageList(NewIndex)` | URL of an XML list; per message `Index`, `Tam`, `Number`, `Name`, `Date`, `Duration`, `New`, `Path` [12, 14] |
| Mark as listened | `X_AVM-DE_TAM:1` `MarkMessage` | – [12] |
| Delete message | `X_AVM-DE_TAM:1` `DeleteMessage` | – [12] |

- **Downloading recordings:** `Path` points to
  `/download.lua?path=/data/tam/rec/rec.0.NNN` [14]. The download needs the session ID
  (`sid`). It is contained in the URL that `GetMessageList` returns. That is a
  conclusion from the structure of these URLs, not officially documented.
- **Format of the recordings: open.** The push service sends answering machine messages
  as WAV [15]. According to a forum post, the files on the box have a different format
  (Speex is mentioned, unconfirmed) [15]. Omafon plays WAV directly and converts
  everything else with `ffmpeg`. If neither works, the phone says
  „Abspielen geht leider nicht“ (“playing doesn’t work, unfortunately”).
- **Access:** a dedicated Fritz!Box user with only the right “voice messages, fax
  messages, FRITZ!App Fon and call list”. TR-064 must be allowed under *Home Network →
  Network → Network Settings*.
- **Library:** `fritzconnection` (Python, in Debian as `python3-fritzconnection`) handles
  SOAP and authentication [16, 17]. Check the service names on your own box with
  `fritzconnection -a fritz.box -s` [17]. On some models they are named differently [17].
- **Alternative for call events:** the call monitor on TCP port 1012 (enable with
  `#96*5*`) delivers `RING/CALL/CONNECT/DISCONNECT` [18]. We don’t need it because
  baresip reports the calls itself.

## 3. DECT modules for DIY builds

| Module | What it is | Approval | Assessment |
|---|---|---|---|
| Dialog/Renesas **SC14CVMDECT** (“Cordless Voice Module”) | radio and baseband, GAP protocol stack, control via a host interface [8, 9] | EU DECT (ETSI), FCC, J-DECT pre-certified [8]. According to the manufacturer only for handsets [8]. **With software other than the standard software, the end device must be re-certified** [8] | the only somewhat openly documented module. Documents 2011–2015, availability unclear [10] |
| DECT ULE modules | data radio for sensors | – | no voice handsets |
| DECT NR+ (e.g. Nordic nRF91 series) | DECT-2020, data radio | – | not GAP-compatible, no voice to the Fritz!Box [7] |

**Result:** there are approved modules, but no maker-friendly chain of module,
development board and documentation that is reliably available today. Add RF layout,
antenna and the question of the end device’s conformity.

## 4. Approval (Radio Equipment Act / RED)

- The German Radio Equipment Act (FuAG) governs **making available on the market “in
  the course of a commercial activity”** and placing on the market. The obligations
  (declaration of conformity, CE, technical documentation) fall on the manufacturer [19].
- Whether a **purely private one-off build** without passing it on is covered is not
  clear from the legal texts [19]. **Open question** (BNetzA or a specialist lawyer).
- **Wi-Fi path:** the radio module of the Pi Zero 2 W stays unchanged with its PCB
  antenna. The well-known modification to an external antenna (U.FL) **voids the radio
  approval** [20]. Hence no external antenna. If the Wi-Fi coverage is weak, a
  Fritz!Repeater helps.
- **DECT path:** custom firmware on the module means re-certification [8]. Even a
  private resale or passing it on would make you the manufacturer [19].

## 5. Other options, named honestly

- **A ready-made senior DECT phone on the Fritz!Box:** dealers describe e.g. the
  Gigaset E560A with “talking keys” and an SOS key [21]. Its own base is connected
  **analog** to the Fritz!Box (FON port), then all of the manufacturer’s functions work
  [22]. I could not confirm the spoken key announcement in a manufacturer source.
  Announcing names, time and answering machine messages, voice dialing and the
  emergency chain are missing.
  *Good as a comparison and as an emergency backup device, not as a replacement for
  Omafon.*
- **Fritz!App Fon on a smartphone** with a screen reader: cheap, but too complex for
  almost blind people without smartphone experience.
- **Pi plus Bluetooth to a DECT handset:** Bluetooth only exists on a few models, often
  limited [6]. Two devices, two batteries, more sources of error.

## 6. Assessment

| | **A: Wi-Fi SIP with Pi Zero 2 W** (recommended) | **B: DIY DECT handset** | *Comparison: ready-made senior DECT* |
|---|---|---|---|
| **Effort** | Medium. The software exists (baresip, TR-064, simulator, tests). Hardware = mobile variant without modem plus cradle | Very high. Module sourcing (B2B), host protocol, RF layout, antenna; the Pi is still needed | none |
| **Approval** | uncritical as long as the Pi’s radio module stays unchanged (no external antenna) [20] | re-certification with custom firmware [8]; open for a one-off build [19] | CE present |
| **Audio quality** | Good. Codecs G.722 (HD) and G.711. Depends on the Wi-Fi quality; stable from about −67 dBm, below that dropouts are possible (experience, unverified) | DECT is very robust against interference; HD only with CAT-iq, uncertain with a third-party GAP device [6] | good, amplifier function for the hearing impaired |
| **Battery life** | Weak point: approx. 14–19 h standby with 3000 mAh (calculation in festnetz-hardware.md); must go into the cradle daily | the radio part is frugal, but the Pi eats the same energy, so **hardly better than A** | days |
| **Cost (material)** | approx. €150–190 | module plus development board unclear (probably much more expensive), plus the rest of A | approx. €50–90 |
| **Functions for AMD** | everything from Omafon: digit, name and time announcements, reading out the answering machine, voice dialing, emergency chain | like A | key announcement (according to the dealer), SOS key |

### Recommendation

**Option A.** It uses the existing software almost unchanged, needs no radio approval
of its own and costs less than the mobile variant. The cradle compensates for the
battery drawback. The phone “lives” there, answers calls when lifted and hangs up when
put back. A ready-made senior DECT phone on a second FON port of the Fritz!Box is a
sensible **backup device** in case Omafon fails.

## 7. What to set up in the Fritz!Box

1. *Telephony → Telephony Devices → New Device → Telephone → LAN/WLAN (IP phone)*,
   name “Omafon”. Enter user name and password in `config.yaml` under `sip:`.
2. Set the outgoing number and the numbers Omafon should ring for.
3. *System → FRITZ!Box Users*: user “omafon” with only the right “voice messages, fax
   messages, FRITZ!App Fon and call list”, enter it in `config.yaml` under `fritz:`.
4. *Home Network → Network → Network Settings*: “Allow access for applications”
   (TR-064) on.
5. Switch on the answering machine. Make the greeting delay long enough for grandma to
   reach the phone in time (e.g. 30 s).
6. *Telephony → Dialing Rules*: check that 110 and 112 go via the landline [3, 23].
   According to forums this is the default, but there is no guarantee [23].
7. Wi-Fi 2.4 GHz on. Don’t put Omafon in the guest network.

## Open questions (also in the pull request)

1. **Fritz!Box model and FRITZ!OS version?** TR-064 service names and the answering
   machine format may differ. Check with `fritzconnection -a fritz.box -s` on the Pi.
2. **Format of the answering machine recordings** via `download.lua` (WAV or something
   else)? Download the first message and look at it with `file`.
3. **Emergency calls via the IP phone:** does 112 really go via the landline, and does
   the provider transmit the address? Ask the provider, check the dialing rule. Don’t
   dial 112 as a test.
4. **Legal situation of a one-off build** (FuAG/RED) for a privately used device with an
   unchanged Pi radio module.
5. **Hands-free in the cradle** needs echo cancellation. baresip has modules for that
   (e.g. WebRTC AEC); check on the real device.
6. **baresip details:** whether `stopringing` reliably stops baresip’s own ringtone and
   `netroam` re-registers after a Wi-Fi change can only be checked on the Pi.

## Sources

1. AVM help: Connecting an IP Telephone to the FRITZ!Box (7590) – https://service.avm.de/help/en/FRITZ-Box-7590/019/hilfe_fon_howto_ip-telefon
2. IP-Telefon an FRITZ!Box anmelden (guide, PDF, German) – https://www.mikrocontroller.net/attachment/73061/IP-Telefon_an_FRITZ_Box_anmelden.PDF
3. AVM help 7590 (IP phones domestic and emergency only by default) – https://service.avm.de/help/en/FRITZ-Box-7590/015/hilfe_fon_howto_ip-telefon
4. AVM/FRITZ! interfaces for developers (TR-064, X_AVM-DE_OnTel, X_AVM-DE_TAM) – https://fritz.com/en/pages/interfaces
5. FRITZ! Knowledge Base: functions with cordless phones (GAP) – https://fritz.com/en/apps/knowledge-base/FRITZ-Box-4690/40_Functions-and-features-that-can-be-used-with-cordless-phones
6. ip-phone-forum.de: Gigaset E720 on Fritz!Box 7490 / third-party DECT – https://www.ip-phone-forum.de/threads/gigaset-e720-%C3%BCber-dect-an-fritz-box-7490.326322/ and https://www.ip-phone-forum.de/showthread.php?p=909633
7. Wikipedia: DECT (DECT-2020 NR) – https://en.wikipedia.org/wiki/DECT ; FRITZ! Knowledge Base: GAP troubleshooting – https://uk.fritz.com/service/knowledge-base/dok/FRITZ-Box-5490/40_Functions-and-features-that-can-be-used-with-cordless-phones/
8. Dialog Semiconductor: SC14CVMDECT SF Datasheet Rev. 3.0 (2015) – https://www.mouser.com/ds/2/713/sc14cvmdect_sf_datasheet_3.0_final_0-908537.pdf
9. FCC ID Y82-SC14S, User Manual CVMDECT – https://fccid.io/Y82-SC14S/User-Manual/user-manual-CVMDECT-2324864
10. Avnet Silica: Renesas Cordless Voice Module SC14CVMDECT (2018) – https://my.avnet.com/silica/products/new-products/npi/2018/dialog-smartbond-cvm/
11. avmtools Wiki: Get-AvmOnTelCallList – https://github.com/chikenborgir/avmtools/wiki/Get-AvmOnTelCallList
12. avmtools: TAM.ps1 (X_AVM-DE_TAM actions) – https://powershellgallery.com/packages/avmtools/3.148.44/Content/Functions/Generic/TAM.ps1
13. CNX Software: Raspberry Pi Zero 2 W power consumption – https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/
14. ioBroker forum: TR-064 Fritzbox answering machine (path rec.0.NNN) – https://forum.iobroker.net/topic/14288/tr-064-fritzbox-anrufbeantworter/20
15. ip-phone-forum.de: downloading voice messages from the box / encoder – https://www.ip-phone-forum.de/threads/sprachnachrichten-von-der-box-laden.191564/ and https://www.ip-phone-forum.de/threads/fritz-box-anrufbeantworter-encoder-decoder.156186/
16. Debian package python3-fritzconnection – https://packages.debian.org/de/sid/all/python3-fritzconnection
17. fritzconnection (GitHub, docs) – https://github.com/kbr/fritzconnection ; MagicMirror forum (service name per model) – https://forum.magicmirror.builders/post/12782
18. fritzconnection: Call Monitoring – https://fritzconnection.readthedocs.io/en/1.9.1/sources/call_monitoring.html
19. Radio Equipment Act (FuAG) – https://www.gesetze-im-internet.de/fuag/__7.html ; IHK Nürnberg fact sheet on radio equipment 2023 – https://www.ihk-nuernberg.de/fileadmin/IHK_Nuernberg/Innovation-Technologie-Forschung/Dokumente/2023_MB_Funkanlagen_final.pdf
20. Brian Dorey: Raspberry Pi Zero 2 W external antenna mod – https://www.briandorey.com/post/raspberry-pi-zero-2-w-external-antenna-mod ; note on certification: https://www.briandorey.com/post/raspberry-pi-zero-w-external-antenna-mod
21. Dealer information Gigaset E560A (talking keys, SOS) – https://www.homeandsmart.de/dect-schnurlos-telefon-test-vergleich
22. Gigaset E560A user manual (SOS key on the base, analog connection) – https://gse.gigaset.com/fileadmin/legacy-assets/CustomerCare/Manuals/E5x/E560A/A31008-M2745-B101-1-19_de_DE-LU.pdf
23. ip-phone-forum.de: emergency numbers in the dialing rules – https://www.ip-phone-forum.de/threads/notrufnummern-aus-wahlregeln-entfernen.108934/latest ; o2 Community: emergency 110/112 not possible (7590) – https://hilfe.o2online.de/dsl-kabel-glasfaser-router-software-internet-telefonie-34/notruf-110-und-112-nicht-moeglich-486280
24. baresip source code: ctrl_tcp, menu (dial/accept/hangup/sndcode), event names – https://github.com/baresip/baresip/blob/main/modules/ctrl_tcp/ctrl_tcp.c , https://github.com/baresip/baresip/blob/main/modules/menu/static_menu.c , https://github.com/baresip/baresip/blob/main/src/bevent.c
