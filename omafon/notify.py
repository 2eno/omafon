"""Notifications without SMS: Telegram bot and/or e-mail.

Replacement for emergency SMS and dictated messages in landline mode. Everything
is optional and off by default. Recipients are the contacts from config.yaml
with ``telegram_chat_id`` and/or ``email``.

config.yaml:
  notify:
    enabled: true
    telegram_token: "123456:ABC…"       # bot from @BotFather
    smtp_host: smtp.example.org         # optional
    smtp_port: 587
    smtp_user: omafon@example.org
    smtp_password: "…"
    smtp_from: omafon@example.org
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.message import EmailMessage

from .telephony import ModemError

log = logging.getLogger("omafon.notify")


class Notifier:
    def __init__(self, cfg, opener=None, smtp_factory=None):
        self.cfg = cfg
        opts = getattr(cfg, "notify", None) or {}
        self.enabled = bool(opts.get("enabled"))
        self.token = opts.get("telegram_token") or ""
        self.smtp = {k[5:]: v for k, v in opts.items() if k.startswith("smtp_")}
        self._open = opener or urllib.request.urlopen
        self._smtp_factory = smtp_factory or smtplib.SMTP

    def can_reach(self, number: str) -> bool:
        c = self.cfg.by_number(number)
        return bool(self.enabled and c and ((self.token and getattr(c, "telegram_chat_id", None))
                                            or (self.smtp.get("host") and getattr(c, "email", None))))

    async def send_to_number(self, number: str, text: str) -> None:
        """Sends text to the contact with this phone number. Raises ModemError
        if no path to them is set up or all paths fail."""
        if not self.enabled:
            raise ModemError("Benachrichtigungen sind ausgeschaltet")
        c = self.cfg.by_number(number)
        if not c:
            raise ModemError(f"Kein Kontakt mit Nummer {number}")
        loop = asyncio.get_running_loop()
        errors, sent = [], False
        if self.token and getattr(c, "telegram_chat_id", None):
            try:
                await loop.run_in_executor(None, self._telegram, c.telegram_chat_id, text)
                sent = True
            except Exception as e:  # network, bot blocked …
                errors.append(f"Telegram: {e}")
        if self.smtp.get("host") and getattr(c, "email", None):
            try:
                await loop.run_in_executor(None, self._mail, c.email, text)
                sent = True
            except Exception as e:
                errors.append(f"E-Mail: {e}")
        if not sent:
            raise ModemError("; ".join(errors) or f"Kein Benachrichtigungsweg zu {c.name}")
        for e in errors:
            log.warning("Partially failed: %s", e)

    def _telegram(self, chat_id, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        with self._open(urllib.request.Request(url, data=data), timeout=15) as r:
            if not json.loads(r.read()).get("ok"):
                raise ModemError("Telegram hat abgelehnt")

    def _mail(self, to: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.smtp.get("from") or self.smtp.get("user")
        msg["To"] = to
        msg["Subject"] = text.split(".")[0][:60] or "Omafon"
        msg.set_content(text)
        with self._smtp_factory(self.smtp["host"], int(self.smtp.get("port", 587)), timeout=20) as s:
            s.starttls(context=ssl.create_default_context())
            if self.smtp.get("user"):
                s.login(self.smtp["user"], self.smtp.get("password", ""))
            s.send_message(msg)
