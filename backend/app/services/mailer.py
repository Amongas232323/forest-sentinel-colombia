"""Envío por SMTP con plantillas HTML de Jinja2 (+ alternativa en texto plano)."""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "email"
_env = Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)


@dataclass
class Attachment:
    filename: str
    content: bytes
    maintype: str
    subtype: str


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    template: str
    context: dict[str, Any]
    attachments: list[Attachment] = field(default_factory=list)
    list_unsubscribe: str | None = None


def render(template: str, context: dict[str, Any]) -> tuple[str, str]:
    s = get_settings()
    ctx = {"web_url": s.public_web_url, "controller": s.privacy_controller_name, **context}
    html = _env.get_template(f"{template}.html").render(**ctx)
    text = _env.get_template(f"{template}.txt").render(**ctx)
    return html, text


def build_message(mail: OutgoingEmail) -> EmailMessage:
    s = get_settings()
    html, text = render(mail.template, mail.context)
    msg = EmailMessage()
    msg["From"] = s.mail_from
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    msg["Message-ID"] = make_msgid(domain="forest-sentinel.local")
    if mail.list_unsubscribe:
        msg["List-Unsubscribe"] = f"<{mail.list_unsubscribe}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    for a in mail.attachments:
        msg.add_attachment(a.content, maintype=a.maintype, subtype=a.subtype, filename=a.filename)
    return msg


def send(mail: OutgoingEmail) -> None:
    s = get_settings()
    msg = build_message(mail)
    if s.smtp_ssl:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=ssl.create_default_context()) as smtp:
            _login_and_send(smtp, msg)
        return
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        if s.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        _login_and_send(smtp, msg)


def _login_and_send(smtp: smtplib.SMTP, msg: EmailMessage) -> None:
    s = get_settings()
    if s.smtp_username and s.smtp_password:
        smtp.login(s.smtp_username, s.smtp_password)
    smtp.send_message(msg)
