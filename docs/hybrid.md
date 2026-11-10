# Hybrid device: landline at home, mobile on the go

*English · [Deutsch](hybrid.de.md)*

An Omafon that works **at home** as a cordless phone on the Fritz!Box
(Wi-Fi/SIP, landline number, answering machine, cradle) and **on the go** as a mobile
phone (LTE, mobile number, SMS, GPS). For the person there is **one** device with
**one** way of using it. The device decides by itself which path is used for a call.

`backend: hybrid` – code in `omafon/hybrid.py`, example in
`config.hybrid.example.yaml`, tests in `tests/test_hybrid.py`.
Try it without hardware (the simulator commands are German):

```bash
python3 -m omafon.main --config config.hybrid.example.yaml --sim
# !wlan aus/an = leave/enter home   !netz aus/an = dead zone
# !ring = landline (at home)   !mring = mobile number   !sms = SMS   !ab = answering machine
```

## 1. Why hybrid?

| Situation | landline only | mobile only | **Hybrid** |
|---|---|---|---|
| At home, normal call | ✔ landline, answering machine | ✔ (reception indoors?) | ✔ via Fritz!Box |
| Garden, edge of the flat | Wi-Fi drops | ✔ | ✔ switches to mobile when Wi-Fi is weak |
| Shopping, doctor, visiting family | ✘ | ✔ | ✔ |
| Power cut / Fritz!Box hangs | ✘ | ✔ | ✔ mobile automatically |
| Dead zone in the house (basement, thick walls) | ✔ | ✘ | ✔ |
| Emergency call at home | ✔ line address | GPS often poor indoors | ✔ landline first, mobile as fallback |
| Emergency call on the go | ✘ | ✔ GPS via SMS | ✔ |

The main gain is **resilience**: two independent paths are available for an
emergency call.

## 2. Behavior (decision table)

| Event | Rule | Why |
|---|---|---|
| Normal call, at home | Fritz!Box, mobile immediately on error | landline flat rate, good voice quality indoors |
| Normal call, Wi-Fi weaker than −75 dBm | mobile first | the call would drop at the edge of the Wi-Fi |
| Normal call, on the go | mobile | – |
| **110/112**, at home | landline first, then mobile | the provider transmits the line address |
| **110/112**, on the go/dead zone | mobile, **even without our own network** | emergency calls go through any available network |
| Ringing on one path | the call belongs to that path | – |
| Ringing on the other path during a call | **reject** (the caller hears busy or reaches the mailbox/answering machine) | call waiting without a display is too confusing for the target group |
| SMS | via mobile; without a network push (Telegram/e-mail) if set up | – |
| Answering machine message (Fritz!Box) and SMS | one shared inbox, same notification (gong, LED) | one way of using it |
| Emergency notice | SMS to the emergency contacts; at home with `home_position`, on the go with a GPS link | – |
| Fritz!Box gone, mobile available | **no** announcement (optionally “Unterwegs …” with `announce_mode`) | on the go that is the normal case |
| Both paths gone | after 10 s „Kein Netz. Telefonieren geht gerade nicht. Ich versuche es weiter.“ (“No network. Calling isn’t possible right now. I keep trying.”), reminder every 10 min, at night only on a key press | never without feedback |
| Info key | „Zu Hause. Verbindung zur Fritzbox gut. Mobilfunk: Empfang gut.“ (“At home. Connection to the Fritzbox good. Mobile: reception good.”) | the state can be queried at any time |

Phone itself stays unchanged except for one thing: the backend may decide which text
from the P dict is spoken for “no connection”.

## 3. Phone numbers – what the family needs to know

The device has **two numbers**: landline and mobile. Three modes:

| `home_modem` | Reachable at home via | Battery | Setup |
|---|---|---|---|
| `"on"` (default) | landline **and** mobile | approx. 0.1 W more in standby | none |
| `"off"` (power saving) | landline; mobile calls only with call forwarding | mobile rests (airplane mode) when the Fritz!Box has been stable for 5 min | with the mobile provider, **call forwarding “when unreachable” to the landline number** (GSM code `**62*<landline number>#`) |
| *Future extension* | landline calls forwarded to the mobile on the go | – | switch Fritz!Box call forwarding on when leaving and off when coming home via TR-064 (`X_AVM-DE_OnTel` knows call forwarding; not implemented, mind the cost of forwarding) |

Recommendation: **`"on"`**. Power saving only saves about 15 % of the standby power
(the Pi needs approx. 0.6 W, the modem at rest approx. 0.1 W). In exchange, SMS are
delayed at home, and an emergency call via mobile first has to wake the modem. Even
112 needs a few seconds after switching on until a cell is found; normal calls only
work after network registration (up to approx. 45 s).
The code wakes the modem automatically for emergency SMS, mobile dialing and GPS.

The mobile provider’s mailbox should be **off** or forward to the landline answering
machine. Omafon only reads out the Fritz!Box answering machine.

## 4. Limitations

- **No handover during a call.** Whoever leaves home during a Wi-Fi call loses the
  connection. The device then says „Gespräch beendet“ (“call ended”) like for any drop.
  A callback via mobile would be possible but was deliberately not automated (double
  calls, cost) → open question. The Wi-Fi threshold (`weak_wifi_dbm`) reduces the
  problem.
- **Two caller numbers.** Whoever gets called sees the landline or the mobile number
  depending on the path. Both belong in the family’s contacts.
- **There is no call waiting.** A second caller on the other path is rejected.

## 5. Hardware

The basis is the **mobile hardware** (SIM7600E-H) **plus the cradle** of the landline
variant. Details on cradle, contacts and relay:
[festnetz-hardware.md](festnetz-hardware.md).

### Differences from the landline variant

| Part | Hybrid | approx. € |
|---|---|---|
| Waveshare SIM7600E-H 4G HAT | mobile, GNSS | 90–100 |
| LTE FPC antenna(s) to glue in (main, optional diversity) | instead of rod antennas | 5–10 |
| Active GNSS ceramic antenna 25 × 25 mm | GPS for emergency calls on the go | 5–8 |
| Boost converter 5 V **3 A** (instead of 1 A) | modem transmit peaks up to 2 A | 10–12 |
| LiPo **4000–5000 mAh** (instead of 3000 mAh) | standby | 15–20 |
| Nano/micro SIM with a voice plan | – | contract |
| **Total** | landline handset + these parts + cradle | **approx. 270–320** |

### Power budget

| State | Power (estimate) |
|---|---|
| Pi idle, Wi-Fi connected | approx. 0.60 W |
| SIM7600 idle, registered | approx. 0.10 W (less with sleep mode AT+CSCLK and the DTR line) |
| Rest (amplifier off, MCP23017, battery IC, LED) | approx. 0.03 W |
| **Total standby** | **approx. 0.73 W** (power saving at home: approx. 0.63 W) |

5000 mAh × 3.7 V × 85 % ≈ 15.7 Wh → **approx. 21 h standby**
(3000 mAh: approx. 13 h). The phone still belongs in the cradle at night. The battery
warnings at 20/10/5 % are spoken.

### Antennas in the handset

```
   ┌──────────────┐  top:    GNSS patch (towards the sky), Pi's Wi-Fi PCB antenna
   │ GNSS    WLAN │          ≥ 20 mm apart
   │              │
   │   keys       │  middle: keypad, Pi, modem HAT
   │              │
   │ battery(back)│  never put the battery over an antenna
   │ LTE FPC      │  bottom: LTE main antenna, as far from the head as possible
   └──────────────┘
```

- LTE at the bottom, i.e. at the chin instead of the ear during a call: less radiation
  towards the head.
- **Don’t modify** the Pi’s PCB antenna (radio approval, see
  [festnetz-recherche.md](festnetz-recherche.md#4-approval-radio-equipment-act--red)).
- LTE band 7 (2.6 GHz) is close to Wi-Fi (2.4 GHz). Distance and the filters in the
  modem are usually enough; if there is interference in testing, move the LTE antenna
  further away.

### Housing and cradle

- Because of the HAT and the larger battery, the handset is **6 mm thicker** (36 instead
  of 30 mm). Housing and cradle take this from `variante="hybrid"` in
  `cad/omafon_masse.scad`. The finished print package is in the CI artifact under
  `gehaeuse/hybrid/` and `ladeschale/hybrid/`. Parts list and assembly:
  [druckteile.md](druckteile.md).
- The SIM card sits in the HAT above the Pi. To change it, open the housing
  (4 screws at the back). That is rarely needed, and grandma never has to touch it.

## 6. Open questions

1. **SAR/radiation at the head:** a self-built LTE phone is not SAR-tested. Antenna at
   the bottom, volume good enough for hands-free. The same applies to any self-built
   LTE device.
2. **Power saving or not?** (recommendation “on”) and whether the provider reliably
   performs call forwarding “when unreachable”.
3. **Automatic callback via mobile** after a Wi-Fi drop during a call: wanted?
4. **Fritz!Box call forwarding on the go** (landline → mobile via TR-064): wanted?
   May cost fees depending on the plan.
5. **Which path for the emergency call when Wi-Fi is weak but mobile is good?**
   Implemented is mobile (a stable connection over address transmission). Alternative:
   landline first anyway.
6. All open questions from [festnetz-recherche.md](festnetz-recherche.md#open-questions-also-in-the-pull-request)
   still apply (answering machine format, emergency calls via an IP phone, baresip on
   the Pi).
