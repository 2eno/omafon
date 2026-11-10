"""State machine of the phone.

All events (keys, modem, one-second tick) arrive through ONE queue.
Event handlers never block: short announcements run as their own tasks
(speak), long flows (voice dialing, dictation, emergency call) as a "job"
that the hang-up key can cancel at any time.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from .hardware import KeyEvent
from .modem import ModemError, ModemEvent
from .numbers import (DIGIT_WORDS, count_words, normalize, signal_words,
                      spoken_date, spoken_number, spoken_time)

log = logging.getLogger("omafon.phone")
DIGITS = set("0123456789*#")


class S(Enum):
    IDLE = auto()        # idle
    ENTRY = auto()       # number is being entered
    VOICE_DIAL = auto()  # "Whom do you want to call?"
    OUTGOING = auto()    # ringing at the other end
    IN_CALL = auto()
    RINGING = auto()     # incoming call
    READING = auto()     # reading SMS aloud
    DICTATE = auto()     # dictating an SMS (recording)
    CONFIRM = auto()     # confirming a dictated SMS
    SOS = auto()         # emergency call


# Fixed announcements (spoken German) – pre-rendered by tools/prerender.py.
P = {
    "ready": "Telefon ist bereit.",
    "deleted": "gelöscht",
    "entry_cleared": "Eingabe gelöscht.",
    "cancelled": "Abgebrochen.",
    "hung_up": "Aufgelegt.",
    "call_ended": "Gespräch beendet.",
    "busy": "Besetzt.",
    "not_reached": "Nicht erreicht.",
    "rejected": "Anruf abgelehnt.",
    "who_call": "Wen möchtest du anrufen? Sag den Namen.",
    "not_understood": "Das habe ich nicht verstanden. Drück nochmal die gelbe Taste.",
    "no_contacts": "Bitte zuerst eine Nummer eintippen.",
    "who_msg": "An wen geht die Nachricht? Sag den Namen.",
    "speak_now": "Sprich jetzt deine Nachricht nach dem Ton. Wenn du fertig bist, mach eine Pause.",
    "nothing_heard": "Ich habe nichts verstanden. Nachricht abgebrochen.",
    "confirm_hint": "Gelbe Taste: senden. Info: nochmal hören. Taste eins: neu sprechen. "
                    "Schwarze Taste: verwerfen.",
    "sending": "Wird gesendet.",
    "sent": "Nachricht gesendet.",
    "send_failed": "Senden hat nicht geklappt. Bitte später nochmal.",
    "discarded": "Nachricht verworfen.",
    "no_messages": "Keine Nachrichten vorhanden.",
    "no_more": "Keine weiteren Nachrichten.",
    "read_hint": "Taste Nachricht: nächste. Info: wiederholen. Gelbe Taste: zurückrufen.",
    "reading_end": "Nachrichten beendet.",
    "hangup_hold": "Zum Auflegen die schwarze Taste etwas länger drücken.",
    "speaker_on": "Lautsprecher an.",
    "speaker_off": "Lautsprecher aus.",
    "unknown_caller": "Anruf von einer unbekannten Nummer.",
    "hidden_caller": "Anruf mit unterdrückter Nummer.",
    "entry_first": "Gib erst die Nummer ein oder lösche sie mit der schwarzen Taste.",
    "sos_cover": "Notruf. Halte den Knopf darunter drei Sekunden gedrückt.",
    "sos_start": "Notruf wird ausgelöst. Schwarze Taste bricht ab.",
    "sos_running": "Notruf läuft.",
    "sos_cancel": "Notruf abgebrochen.",
    "sos_done": "Notruf beendet. Rückrufe werden automatisch angenommen.",
    "sos_nobody": "Ich habe niemanden erreicht. Alle Notfallkontakte haben eine SMS bekommen.",
    "modem_restart": "Das Mobilfunkteil startet neu. Bitte einen Moment warten.",
    "modem_dead": "Achtung, Telefonieren ist gerade nicht möglich.",
    # Landline (backend: sip)
    "link_lost": "Keine Verbindung zur Fritzbox. Ich versuche es weiter.",
    "link_ok": "Verbindung zur Fritzbox ist wieder da.",
    "voicemail": "Nachricht auf dem Anrufbeantworter.",
    "voicemail_unplayable": "Nachricht auf dem Anrufbeantworter. Abspielen geht leider nicht.",
    "no_sending": "Nachrichten verschicken ist bei diesem Telefon nicht eingerichtet.",
    "no_sending_to": "An diese Person kann ich keine Nachricht schicken.",
    # Hybrid (backend: hybrid)
    "no_network": "Kein Netz. Telefonieren geht gerade nicht. Ich versuche es weiter.",
    "network_ok": "Telefonieren geht wieder.",
    "mode_home": "Zu Hause. Telefon über die Fritzbox.",
    "mode_mobile": "Unterwegs. Telefon über Mobilfunk.",
}


@dataclass
class Call:
    number: str | None
    incoming: bool
    answered: asyncio.Event = field(default_factory=asyncio.Event)
    ended: asyncio.Event = field(default_factory=asyncio.Event)
    speaker: bool = False
    reason: str = ""
    hold_hint: bool = False      # "press longer" hint already given


class Phone:
    def __init__(self, cfg, audio, modem, stt, hw, events: asyncio.Queue, clock=dt.datetime.now):
        self.cfg, self.audio, self.modem, self.stt, self.hw = cfg, audio, modem, stt, hw
        self.events, self.now = events, clock
        self.state = S.IDLE
        self.number = ""
        self.call: Call | None = None
        self.job: asyncio.Task | None = None
        self.ring_task: asyncio.Task | None = None
        self._bg: set[asyncio.Task] = set()
        self.last_activity = self.now()
        self.last_ring = self.now()
        self.data = Path(cfg.data_dir)
        self.data.mkdir(parents=True, exist_ok=True)
        self.inbox: list[dict] = self._load("inbox.json", [])
        self.missed: list[dict] = self._load("missed.json", [])
        self.partial: dict[tuple, dict] = {}
        self.playlist: list[int] = []
        self.read_pos = 0
        self.next_news_signal: dt.datetime | None = None   # next reminder gong
        self.led_on = False
        self.pending_dial: str | None = None
        self.draft_to: str | None = None
        self.draft_text = ""
        self.callback_until: dt.datetime | None = None
        self.sos_counting = False
        self.battery_warned: set[int] = set()
        self.modem_failures = 0
        self.ticks = 0
        self.link_reminder: dt.datetime | None = None    # connection lost: next reminder

    # ================================================================ Basics
    def _load(self, name, default):
        try:
            return json.loads((self.data / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _save(self, name, obj) -> None:
        tmp = self.data / (name + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.data / name)   # atomic: no half-written JSON after a power cut

    def bg(self, coro) -> asyncio.Task:
        """Background task with a strong reference (otherwise asyncio may lose it)."""
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)
        return t

    def speak(self, text: str) -> None:
        """Announcement without waiting; interrupts the current one."""
        self.bg(self.audio.say(text))

    def start_job(self, coro) -> None:
        self.cancel_job()
        self.job = asyncio.create_task(self._guard(coro))
        self.job.add_done_callback(lambda _t: coro.close())  # never started -> close cleanly

    def cancel_job(self) -> None:
        if self.job and not self.job.done() and self.job is not asyncio.current_task():
            self.stt.stop_flag.set()
            self.job.cancel()

    async def _guard(self, coro) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Error in flow")
            await self.audio.say("Es ist ein Fehler aufgetreten.")
            self.go_idle()

    def go_idle(self) -> None:
        self.state = S.IDLE
        self.number = ""
        self.pending_dial = None
        self.audio.route("speaker")

    def name_or_number(self, number: str | None) -> str:
        if not number:
            return "unbekannt"
        return self.cfg.name_for(number) or spoken_number(number)

    def quiet_now(self) -> bool:
        start, end = self.cfg.quiet_hours
        h = self.now().hour
        return (h >= start or h < end) if start > end else (start <= h < end)

    # ================================================================ Main loop
    async def run(self) -> None:
        await self.startup()
        while True:
            ev = await self.events.get()
            try:
                await self.handle(ev)
            except Exception:
                log.exception("Error handling event %r", ev)

    async def startup(self) -> None:
        self.audio.route("speaker")
        self.audio.set_volume(self.cfg.volume)
        try:
            for idx in await self.modem.stored_indices():
                await self.on_sms(idx, announce=False)
        except ModemError as e:
            log.warning("Stored SMS not readable: %s", e)
        await self.audio.say(P["ready"])
        if self.unread_count():
            self.next_news_signal = self.now()          # announce on the next tick

    async def handle(self, ev) -> None:
        if isinstance(ev, KeyEvent):
            self.last_activity = self.now()
            await self.on_key(ev)
        elif isinstance(ev, ModemEvent):
            await self.on_modem(ev)
        elif ev == "tick":
            await self.on_tick()

    # ================================================================ Keys
    async def on_key(self, ev: KeyEvent) -> None:
        k, kind = ev.key, ev.kind
        if k in ("VOL_UP", "VOL_DOWN"):
            if kind == "short":
                await self.change_volume(1 if k == "VOL_UP" else -1)
            return
        if k in ("SOS", "SOS_COVER"):
            return self.on_sos_key(k, kind)
        if k == "CHARGER":
            return await self.on_charger(kind)
        if k in DIGITS and kind == "down" and self.state in (
                S.IDLE, S.ENTRY, S.IN_CALL, S.OUTGOING, S.VOICE_DIAL, S.READING):
            self.speak(DIGIT_WORDS[k])
            return
        if kind not in ("short", "long"):
            return
        self.key_held = ev.held
        handler = getattr(self, f"key_{self.state.name.lower()}")
        await handler(k, kind)

    async def key_idle(self, k, kind):
        if k in DIGITS:
            if kind == "long" and k in "123456789":
                c = self.cfg.by_speed_dial(int(k))
                if c:
                    return self.start_job(self.call_job(c.number))
                return self.speak(f"Auf Taste {DIGIT_WORDS[k]} ist niemand gespeichert.")
            self.state, self.number = S.ENTRY, k
        elif k == "CALL":
            if not self.cfg.contacts:
                return self.speak(P["no_contacts"])
            self.start_job(self.voice_dial_job())
        elif k == "HANGUP":
            self.speak(P["ready"])
        elif k == "MSG":
            if kind == "long":
                self.start_job(self.dictate_job(None))
            else:
                self.start_job(self.read_job(start=True))
        elif k == "INFO":
            self.start_job(self.info_job())

    async def key_entry(self, k, kind):
        if k in DIGITS:
            if len(self.number) < 20:
                self.number += k
        elif k == "CALL":
            self.start_job(self.call_job(self.number))
        elif k == "HANGUP":
            if kind == "long" or len(self.number) <= 1:
                self.go_idle()
                self.speak(P["entry_cleared"])
            else:
                self.number = self.number[:-1]
                self.speak(P["deleted"])
        elif k == "INFO":
            name = self.cfg.name_for(self.number)
            self.speak(spoken_number(self.number) + (f". Das ist {name}." if name else "."))
        elif k == "MSG":
            self.speak(P["entry_first"])

    async def key_voice_dial(self, k, kind):
        if k == "HANGUP":
            self.cancel_job()
            self.go_idle()
            self.speak(P["cancelled"])
        elif k == "CALL" and self.pending_dial:
            self.start_job(self.call_job(self.pending_dial))
        elif k in DIGITS:
            self.cancel_job()
            self.state, self.number = S.ENTRY, k

    def hangup_deliberate(self, kind: str) -> bool:
        """During a call, hanging up only counts if the key was held – otherwise
        the cheek brushes the key at the ear. Putting the handset into the
        cradle still hangs up immediately."""
        hold = self.cfg.hangup_hold_s
        if kind == "long" or hold <= 0 or getattr(self, "key_held", 0.0) >= hold:
            return True
        if self.call and not self.call.hold_hint:
            self.call.hold_hint = True
            self.speak(P["hangup_hold"])
        return False

    async def key_outgoing(self, k, kind):
        if k == "HANGUP" and self.hangup_deliberate(kind):
            await self.end_call(P["hung_up"])

    async def key_in_call(self, k, kind):
        if k == "HANGUP":
            if self.hangup_deliberate(kind):
                await self.end_call(P["hung_up"])
        elif k in DIGITS:
            try:
                await self.modem.dtmf(k)
            except ModemError:
                pass
        elif k == "INFO" and self.call:
            self.call.speaker = not self.call.speaker
            self.audio.route("speaker" if self.call.speaker else "earpiece")
            self.speak(P["speaker_on"] if self.call.speaker else P["speaker_off"])

    async def key_ringing(self, k, kind):
        if k == "CALL":
            await self.answer()
        elif k == "HANGUP":
            self.stop_ringing()
            try:
                await self.modem.hangup()
            except ModemError:
                pass
            self.call = None
            self.go_idle()
            self.speak(P["rejected"])
        elif k == "INFO":
            self.speak(self.caller_phrase())

    async def key_reading(self, k, kind):
        if k == "MSG":
            if kind == "long":
                sender = self.inbox[self.playlist[self.read_pos]]["sender"]
                return self.start_job(self.dictate_job(sender))
            self.start_job(self.read_job(start=False, step=1))
        elif k == "INFO":
            self.start_job(self.read_job(start=False, step=0))
        elif k == "CALL":
            sender = self.inbox[self.playlist[self.read_pos]]["sender"]
            self.start_job(self.call_job(sender))
        elif k == "HANGUP":
            self.cancel_job()
            self.go_idle()
            self.speak(P["reading_end"])
        elif k in DIGITS:
            self.cancel_job()
            self.state, self.number = S.ENTRY, k

    async def key_dictate(self, k, kind):
        if k == "HANGUP":
            self.cancel_job()
            self.go_idle()
            self.speak(P["discarded"])
        elif k in ("CALL", "MSG", "INFO"):
            self.stt.stop_flag.set()          # stop recording early

    async def key_confirm(self, k, kind):
        if k == "CALL":
            self.start_job(self.send_job())
        elif k == "INFO":
            self.speak(f"{self.draft_text} {P['confirm_hint']}")
        elif k == "1":
            self.start_job(self.dictate_job(self.draft_to))
        elif k == "HANGUP":
            self.go_idle()
            self.speak(P["discarded"])

    async def key_sos(self, k, kind):
        if k == "HANGUP":
            self.cancel_job()
            if self.call:
                await self.end_call(None)
            self.go_idle()
            self.speak(P["sos_cancel"])

    # ---------------------------------------------------------------- Volume
    async def change_volume(self, delta: int) -> None:
        level = self.audio.set_volume(self.audio.volume + delta)
        if self.state in (S.IN_CALL, S.OUTGOING):
            try:
                await self.modem.call_volume(level)
            except ModemError:
                pass
            self.bg(self.audio.tone("beep"))
        else:
            self.speak(f"Lautstärke {level}.")

    # ---------------------------------------------------------------- Cradle
    async def on_charger(self, kind: str) -> None:
        if kind not in ("down", "up"):
            return
        if self.state == S.RINGING and kind == "up" and self.cfg.answer_on_lift:
            return await self.answer()                # lifting = answering
        if self.state in (S.IN_CALL, S.OUTGOING) and self.call:
            if kind == "down" and self.cfg.dock_in_call == "hangup":
                return await self.end_call(P["hung_up"])    # putting down = hanging up
            if kind == "down" and self.cfg.dock_in_call == "handsfree":
                self.call.speaker = True
                self.audio.route("speaker")
                return self.speak(P["speaker_on"])
            if kind == "up" and self.call.speaker and self.cfg.dock_speaker:
                self.call.speaker = False
                self.audio.route("earpiece")
                return self.speak(P["speaker_off"])
            return
        b = self.hw.battery_percent()
        pct = f" Akku {b} Prozent." if b is not None else ""
        if kind == "down":
            self.battery_warned.clear()
        if self.state == S.IDLE:
            self.speak(("Lädt." if kind == "down" else "Vom Ladegerät genommen.") + pct)

    # ================================================================ Emergency call
    def on_sos_key(self, k: str, kind: str) -> None:
        if self.state == S.SOS:
            return
        if k == "SOS_COVER" and kind == "down":
            self.speak(P["sos_cover"])
        elif k == "SOS" and kind == "down":
            self.sos_counting = True
            self.start_job(self.sos_countdown())
        elif k == "SOS" and kind == "short" and self.sos_counting:
            self.sos_counting = False          # released too early
            self.cancel_job()
            self.go_idle()
            self.speak(P["cancelled"])
        elif k == "SOS" and kind == "long":
            self.sos_counting = False
            self.start_job(self.sos_job())

    async def sos_countdown(self) -> None:
        self.audio.route("speaker")
        for word in ("drei", "zwo", "eins"):
            await self.audio.say(word)
            await self.audio.tone("beep")
            await asyncio.sleep(0.6)

    async def sos_job(self) -> None:
        self.state = S.SOS
        if self.call:                                  # end the current call
            await self.end_call(None)
            self.state = S.SOS
        self.audio.route("speaker")
        self.audio.set_volume(5)
        await self.audio.tone("sos")
        await self.audio.say(P["sos_start"])
        await asyncio.sleep(self.cfg.sos_cancel_window_s)
        await self.audio.say(P["sos_running"])
        if not self.modem.online:                     # try anyway – it may be back in a moment
            await self.audio.say(self.offline_phrase())
        self.bg(self.sos_sms())            # keeps running independently
        chain = self.cfg.emergency_chain()
        targets = [(c.name, c.number) for c in chain] or [("den Notruf", "112")]
        for _round in range(self.cfg.emergency_rounds):
            for name, number in targets:
                await self.audio.say(f"Ich rufe {name} an.")
                call = await self.place_call(number, speaker=True)
                if await self.wait_answer(call, self.cfg.emergency_ring_seconds):
                    await call.ended.wait()
                    self.callback_until = self.now() + dt.timedelta(
                        minutes=self.cfg.emergency_callback_minutes)
                    self.go_idle()
                    await self.audio.say(P["sos_done"])
                    return
                await self.end_call(None)
                self.state = S.SOS
                await asyncio.sleep(2)
        self.callback_until = self.now() + dt.timedelta(minutes=self.cfg.emergency_callback_minutes)
        self.go_idle()
        await self.audio.say(P["sos_nobody"])

    async def sos_sms(self) -> None:
        b = self.hw.battery_percent()
        base = f"NOTRUF von {self.cfg.owner_name}! Bitte sofort melden."
        base += f" Akku {b}%." if b is not None else ""
        numbers = [c.number for c in self.cfg.emergency_chain() if len(normalize(c.number)) > 5]
        for n in numbers:
            try:
                await self.modem.send_sms(n, base)
            except ModemError as e:
                log.error("Emergency SMS to %s: %s", n, e)
        pos = await self.modem.gps_position(60)
        if pos:
            link = f"https://www.openstreetmap.org/?mlat={pos[0]:.5f}&mlon={pos[1]:.5f}&zoom=17"
            for n in numbers:
                try:
                    await self.modem.send_sms(n, f"Standort von {self.cfg.owner_name}: {link}")
                except ModemError:
                    pass

    def callback_active(self) -> bool:
        return bool(self.callback_until and self.now() < self.callback_until)

    # ================================================================ Calls
    def offline_phrase(self) -> str:
        """Announce 'no network' – the text comes from P, the backend picks the key."""
        return P.get(getattr(self.modem, "offline_key", "link_lost"), P["link_lost"])

    def docked_speaker(self) -> bool:
        """If the phone sits in the cradle with the speaker -> hands-free."""
        return bool(self.cfg.dock_speaker and self.hw.on_charger())

    async def place_call(self, number: str, speaker: bool = False) -> Call:
        speaker = speaker or self.docked_speaker()
        self.call = Call(number, incoming=False, speaker=speaker)
        self.audio.route("speaker" if speaker or self.cfg.default_route == "speaker" else "earpiece")
        try:
            await self.modem.dial(number)
        except ModemError as e:
            log.error("Dialing failed: %s", e)
            self.call.reason = "error"
            self.call.ended.set()
        return self.call

    async def wait_answer(self, call: Call, seconds: float) -> bool:
        a = asyncio.create_task(call.answered.wait())
        e = asyncio.create_task(call.ended.wait())
        await asyncio.wait({a, e}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
        a.cancel()
        e.cancel()
        return call.answered.is_set() and not call.ended.is_set()

    async def call_job(self, number: str) -> None:
        number = number.strip()
        if not number:
            return
        if not self.modem.online:
            self.go_idle()
            return await self.audio.say(self.offline_phrase())
        name = self.cfg.name_for(number)
        self.state = S.OUTGOING
        await self.audio.say(f"Ich rufe {name} an." if name else
                             f"Ich wähle {spoken_number(number)}.")
        if self.state != S.OUTGOING:      # hung up in the meantime
            return
        call = await self.place_call(number)
        if call.ended.is_set():
            self.go_idle()
            await self.audio.say(P["not_reached"])

    async def answer(self) -> None:
        self.stop_ringing()
        try:
            await self.modem.answer()
        except ModemError as e:
            log.error("Answer: %s", e)
        if self.call:
            self.call.answered.set()
            self.call.speaker = self.call.speaker or self.docked_speaker()
            self.audio.route("speaker" if self.call.speaker else
                             ("speaker" if self.cfg.default_route == "speaker" else "earpiece"))
        if self.state != S.SOS:
            self.state = S.IN_CALL

    async def end_call(self, phrase: str | None) -> None:
        call = self.call
        self.call = None
        try:
            await self.modem.hangup()
        except ModemError:
            pass
        if call:
            call.reason = call.reason or "local"
            call.ended.set()
        if self.state != S.SOS:
            self.cancel_job()
            self.go_idle()
        if phrase:
            self.speak(phrase)

    def caller_phrase(self) -> str:
        n = self.call.number if self.call else None
        if not n:
            return P["hidden_caller"]
        name = self.cfg.name_for(n)
        return f"Anruf von {name}." if name else P["unknown_caller"]

    async def ring_loop(self) -> None:
        try:
            await asyncio.sleep(0.3)        # wait for +CLIP
            while True:
                self.hw.vibrate(True)
                self.hw.flash(True)
                await self.audio.tone("ring", interrupt=True)
                self.hw.vibrate(False)
                self.hw.flash(False)
                await self.audio.say(self.caller_phrase())
                await asyncio.sleep(1.5)
        finally:
            self.hw.vibrate(False)
            self.hw.flash(False)
            self.led_on = False

    def stop_ringing(self) -> None:
        if self.ring_task and not self.ring_task.done():
            self.ring_task.cancel()
        self.ring_task = None

    # ================================================================ Modem events
    async def on_modem(self, ev: ModemEvent) -> None:
        k = ev.kind
        if k == "ring":
            self.last_ring = self.now()
            if self.call is None:
                self.call = Call(None, incoming=True)
                if self.state != S.SOS:
                    self.cancel_job()           # reading aloud, dictation etc. give way to the call
                    self.state = S.RINGING
                    self.audio.route("speaker")
                    self.ring_task = asyncio.create_task(self.ring_loop())
        elif k == "clip" and self.call and self.call.incoming:
            self.call.number = ev.data or None
            c = self.cfg.by_number(ev.data) if ev.data else None
            if c and c.emergency and (self.callback_active() or self.state == S.SOS):
                self.call.speaker = True    # callback during an emergency: speaker on right away
                self.audio.set_volume(5)
                await self.answer()
        elif k == "call_begin":
            if self.call:
                self.call.answered.set()
            if self.state in (S.OUTGOING, S.RINGING):
                self.stop_ringing()
                self.state = S.IN_CALL
        elif k in ("call_end", "no_carrier", "busy", "no_answer", "missed"):
            await self.on_call_gone(k)
        elif k == "sms":
            try:
                await self.on_sms(int(ev.data))
            except (ValueError, ModemError) as e:
                log.error("SMS %s: %s", ev.data, e)
        elif k == "link_lost":
            # Don't wake anyone at night: a key press or the reminder after the
            # quiet hours says it (link_reminder is already due by then).
            quiet = self.quiet_now()
            self.link_reminder = self.now() + (dt.timedelta(0) if quiet else
                                               dt.timedelta(minutes=self.cfg.link_reminder_minutes))
            if self.state not in (S.IN_CALL, S.SOS) and not quiet:
                self.speak(P.get(ev.data, self.offline_phrase()))
        elif k == "link_ok":
            # data = P key (e.g. network_ok, mode_home); empty = link_ok
            self.link_reminder = None
            if self.state not in (S.IN_CALL, S.SOS) and not self.quiet_now():
                self.speak(P.get(ev.data, P["link_ok"]))

    async def on_call_gone(self, kind: str) -> None:
        call = self.call
        if call is None:
            return
        self.call = None
        call.reason = kind
        call.ended.set()
        if self.state == S.SOS:
            return
        if self.state == S.RINGING and not call.answered.is_set():
            self.stop_ringing()
            self.missed.append({"number": call.number, "time": self.now().isoformat(timespec="minutes")})
            self._save("missed.json", self.missed[-20:])
            self.go_idle()
            self.speak(f"Verpasster Anruf von {self.name_or_number(call.number)}.")
        elif self.state == S.OUTGOING and not call.answered.is_set():
            self.go_idle()
            self.speak(P["busy"] if kind == "busy" else P["not_reached"])
        elif self.state in (S.IN_CALL, S.OUTGOING, S.RINGING):
            self.stop_ringing()
            self.go_idle()
            self.speak(P["call_ended"])

    # ================================================================ SMS
    async def on_sms(self, index: int, announce: bool = True) -> None:
        d = await self.modem.read_sms(index)
        await self.modem.delete_sms(index)
        if d is None:
            return
        text = d.text
        if d.concat_ref is not None and d.concat_total > 1:
            key = (normalize(d.sender), d.concat_ref)
            entry = self.partial.setdefault(key, {"t": self.now(), "parts": {}, "d": d})
            entry["parts"][d.concat_seq] = d.text
            if len(entry["parts"]) < d.concat_total:
                return                                  # wait for further parts
            del self.partial[key]
            text = "".join(entry["parts"][i] for i in sorted(entry["parts"]))
        audio = getattr(d, "audio", None)            # answering machine: path or ""
        if audio is not None:
            text = P["voicemail"] if audio else P["voicemail_unplayable"]
        await self.store_sms(d.sender, text, d.timestamp, announce, audio=audio or "")

    async def store_sms(self, sender: str, text: str, ts, announce: bool = True,
                        audio: str = "") -> None:
        c = self.cfg.by_number(sender)
        if not audio and c and c.admin and text.strip().upper() == "STATUS":
            return await self.send_status(sender)
        msg = {"sender": sender, "text": text.strip(),
               "time": (ts or self.now()).isoformat(timespec="minutes"), "read": False}
        if audio:
            msg["audio"] = audio
        self.inbox.insert(0, msg)
        for old in self.inbox[50:]:                     # delete old recordings too
            if old.get("audio"):
                Path(old["audio"]).unlink(missing_ok=True)
        del self.inbox[50:]
        self._save("inbox.json", self.inbox)
        if not announce:
            return
        # Never read aloud automatically: only gong + LED. Reading happens on a
        # key press (message key). During a call/menu the gong comes afterwards.
        self.next_news_signal = self.now()
        await self.signal_news()

    def unread_count(self) -> int:
        return sum(not m["read"] for m in self.inbox)

    async def signal_news(self) -> None:
        """Gong for unread messages when due and the phone is idle."""
        if not self.unread_count():
            self.next_news_signal = None
            return
        now = self.now()
        if (self.next_news_signal is None or now < self.next_news_signal
                or self.state != S.IDLE or (self.job and not self.job.done())
                or self.quiet_now()):
            return
        self.bg(self.audio.tone("gong"))
        minutes = self.cfg.news_signal_minutes
        self.next_news_signal = now + dt.timedelta(minutes=minutes) if minutes > 0 else None

    def update_news_led(self) -> None:
        """Slow blinking (1 s on, 2 s off) while there is something unread."""
        if self.state == S.RINGING:                     # the LED currently belongs to ringing
            return
        want = bool(self.cfg.news_led and self.unread_count() and self.ticks % 3 == 0)
        if want != self.led_on:
            self.led_on = want
            self.hw.flash(want)

    async def send_status(self, number: str) -> None:
        b = self.hw.battery_percent()
        rssi = await self.modem.signal()
        unread = sum(not m["read"] for m in self.inbox)
        txt = (f"Omafon: Akku {b}%{' (laedt)' if self.hw.on_charger() else ''}, "
               f"Empfang {rssi}/31, ungelesen {unread}, verpasst {len(self.missed)}.")
        try:
            await self.modem.send_sms(number, txt)
        except ModemError as e:
            log.error("Status SMS: %s", e)

    def build_playlist(self) -> list[int]:
        unread = [i for i, m in enumerate(self.inbox) if not m["read"]]
        read = [i for i, m in enumerate(self.inbox) if m["read"]]
        return list(reversed(unread)) + read      # unread oldest first, then the rest

    def when_words(self, iso: str) -> str:
        try:
            t = dt.datetime.fromisoformat(iso)
        except ValueError:
            return ""
        today = self.now().date()
        hm = f"{t.hour} Uhr {t.minute}" if t.minute else f"{t.hour} Uhr"
        if t.date() == today:
            return f"heute um {hm}"
        if t.date() == today - dt.timedelta(days=1):
            return f"gestern um {hm}"
        return f"am {t.day}. {t.month}."

    async def read_job(self, start: bool, step: int = 0, intro: str = "") -> None:
        if start:
            self.playlist, self.read_pos = self.build_playlist(), 0
            if not self.playlist:
                self.go_idle()
                return await self.audio.say(P["no_messages"])
        else:
            self.read_pos += step
            if self.read_pos >= len(self.playlist):
                self.go_idle()
                return await self.audio.say(P["no_more"])
        self.state = S.READING
        self.audio.route("speaker")
        m = self.inbox[self.playlist[self.read_pos]]
        new = not m["read"]
        m["read"] = True
        self._save("inbox.json", self.inbox)
        who = self.name_or_number(m["sender"])
        when = self.when_words(m["time"])
        head = (f"{intro} Von {who}, {when}." if intro else
                f"{'Neue ' if new else ''}Nachricht von {who}, {when}.")
        await self.audio.say(f"{head} {m['text']}")
        if m.get("audio"):
            await self.audio.play(Path(m["audio"]), interrupt=False)
        await asyncio.sleep(0.4)
        await self.audio.say(P["read_hint"])

    # ================================================================ Voice dialing & dictation
    def all_words(self) -> list[str]:
        return [w for c in self.cfg.contacts for w in c.words()]

    async def voice_dial_job(self) -> None:
        self.state = S.VOICE_DIAL
        self.audio.route("speaker")
        await self.audio.say(P["who_call"])
        await self.audio.tone("record")
        heard = await self.stt.listen_name(self.all_words())
        c = self.cfg.by_word(heard)
        if not c:
            self.go_idle()
            return await self.audio.say(P["not_understood"])
        self.pending_dial = c.number
        await self.audio.say(f"{c.name}. Gelbe Taste zum Anrufen.")
        await asyncio.sleep(15)                   # then return automatically
        if self.state == S.VOICE_DIAL:
            self.go_idle()

    async def dictate_job(self, to: str | None) -> None:
        if not self.modem.supports_sms:
            self.go_idle()
            return await self.audio.say(P["no_sending"])
        self.state = S.DICTATE
        self.audio.route("speaker")
        if to is None:
            await self.audio.say(P["who_msg"])
            await self.audio.tone("record")
            c = self.cfg.by_word(await self.stt.listen_name(self.all_words()))
            if not c:
                self.go_idle()
                return await self.audio.say(P["not_understood"])
            to = c.number
        if not self.modem.can_send_to(to):
            self.go_idle()
            return await self.audio.say(P["no_sending_to"])
        self.draft_to = to
        await self.audio.say(f"Nachricht an {self.name_or_number(to)}. {P['speak_now']}")
        await self.audio.tone("record")
        text = await self.stt.dictate()
        if not text:
            self.go_idle()
            return await self.audio.say(P["nothing_heard"])
        self.draft_text = text
        self.state = S.CONFIRM
        await self.audio.say(f"Deine Nachricht an {self.name_or_number(to)} lautet: {text} "
                             f"{P['confirm_hint']}")

    async def send_job(self) -> None:
        await self.audio.say(P["sending"])
        try:
            await self.modem.send_sms(self.draft_to, self.draft_text)
            self.go_idle()
            await self.audio.say(P["sent"])
        except ModemError as e:
            log.error("Sending SMS: %s", e)
            self.state = S.CONFIRM                 # the text is kept
            await self.audio.say(P["send_failed"])

    # ================================================================ Info
    async def info_job(self) -> None:
        now = self.now()
        parts = [spoken_time(now), spoken_date(now)]
        b = self.hw.battery_percent()
        if b is not None:
            parts.append(f"Akku {b} Prozent{', lädt' if self.hw.on_charger() else ''}.")
        parts.append(self.modem.status_words() or signal_words(await self.modem.signal()))
        if self.missed:
            names = [self.name_or_number(m["number"]) for m in self.missed[-3:]]
            parts.append(count_words(len(self.missed), "Ein verpasster Anruf", "verpasste Anrufe", "")
                         + " von " + ", ".join(names) + ".")
            self.missed.clear()
            self._save("missed.json", self.missed)
        unread = sum(not m["read"] for m in self.inbox)
        parts.append(count_words(unread, "Eine neue Nachricht.", "neue Nachrichten.",
                                 "Keine neuen Nachrichten."))
        await self.audio.say(" ".join(parts))

    # ================================================================ One-second tick
    async def on_tick(self) -> None:
        self.ticks += 1
        now = self.now()
        idle_s = (now - self.last_activity).total_seconds()
        if self.state == S.ENTRY and idle_s > self.cfg.entry_timeout_s:
            self.go_idle()
            self.speak(P["entry_cleared"])
        elif self.state in (S.READING, S.CONFIRM) and idle_s > 90 and not (self.job and not self.job.done()):
            if self.state == S.CONFIRM:
                self.speak("Nachricht wurde nicht gesendet.")
            self.go_idle()
        elif self.state == S.RINGING and (now - self.last_ring).total_seconds() > 8:
            await self.on_call_gone("missed")
        for key, entry in list(self.partial.items()):     # incomplete long SMS
            if (now - entry["t"]).total_seconds() > 120:
                del self.partial[key]
                text = " … ".join(entry["parts"][i] for i in sorted(entry["parts"]))
                await self.store_sms(entry["d"].sender, text, entry["d"].timestamp)
        await self.signal_news()
        self.update_news_led()
        if self.link_reminder and now >= self.link_reminder:
            if self.modem.online:
                self.link_reminder = None
            elif self.state == S.IDLE and not self.quiet_now() and not (self.job and not self.job.done()):
                self.speak(self.offline_phrase())
                self.link_reminder = now + dt.timedelta(minutes=self.cfg.link_reminder_minutes)
        if self.ticks % 60 == 0:
            await self.check_battery()
            await self.check_modem()
        if self.ticks % 600 == 0 and idle_s > 600:
            self.stt.unload()

    async def check_battery(self) -> None:
        b = self.hw.battery_percent()
        if b is None or self.hw.on_charger():
            return
        for limit in (5, 10, 20):
            if b <= limit and limit not in self.battery_warned:
                self.battery_warned.update(l for l in (5, 10, 20) if l >= limit)
                if self.state == S.IDLE:
                    self.speak(f"Akku fast leer, noch {b} Prozent. Bitte in die Ladeschale stellen.")
                break

    async def check_modem(self) -> None:
        if self.state not in (S.IDLE, S.READING):
            return
        if await self.modem.alive():
            self.modem_failures = 0
            return
        self.modem_failures += 1
        if self.modem_failures == 3:
            self.speak(P["modem_restart"])
            await self.hw.modem_power_cycle()
            try:
                await self.modem.start()
                self.modem_failures = 0
            except ModemError:
                self.speak(P["modem_dead"])
