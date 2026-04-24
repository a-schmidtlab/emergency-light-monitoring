# Notlicht-Monitor - Emergency Light Monitoring Tool
# Copyright (C) 2026 Axel Schmidt
# SPDX-License-Identifier: LicenseRef-Notlicht-Monitor-NC
#
# Nicht-kommerzielle Nutzung ist frei gestattet. Kommerzielle Nutzung bedarf
# der schriftlichen Zustimmung des Autors. Volle Bedingungen: siehe LICENSE.
#
# HAFTUNGSAUSSCHLUSS: Keine Gewaehrleistung. Diese Software stellt nur ein
# zusaetzliches informationelles Monitoring dar und ERSETZT NICHT die
# gesetzlich vorgeschriebenen Pruefungen der Notlichtanlage durch
# Fachpersonal (DIN EN 50172, VDE 0108, DIN EN 50171, VDE 0100-560,
# DGUV Vorschrift 3 u. a.). Die Verantwortung fuer die ordnungsgemaesse
# Funktion verbleibt beim Betreiber.
"""
SMTP-Versand. Default: SSL (Port 465). STARTTLS als Fallback moeglich.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import List

log = logging.getLogger(__name__)


class Mailer:
    def __init__(self, host: str, port: int,
                 username: str, password: str,
                 from_address: str, from_name: str,
                 use_ssl: bool = True, timeout: int = 30):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.from_name = from_name or from_address
        self.use_ssl = use_ssl
        self.timeout = timeout

    def send(self, recipients: List[str], subject: str, body: str):
        msg = EmailMessage()
        msg["From"] = formataddr((self.from_name, self.from_address))
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid()
        msg.set_content(body)

        context = ssl.create_default_context()
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port,
                                  context=context, timeout=self.timeout) as s:
                if self.username:
                    s.login(self.username, self.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as s:
                s.ehlo()
                s.starttls(context=context)
                s.ehlo()
                if self.username:
                    s.login(self.username, self.password)
                s.send_message(msg)
        log.info("Mail gesendet an %s: %s", recipients, subject)
