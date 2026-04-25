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
IMAP-Inbox-Verarbeitung fuer die TEST-Mail-Funktion.

Workflow pro Lauf:
  1. Verbindung zum IMAP-Server aufbauen (SSL, Port 993).
  2. Alle Mails im Postfach durchgehen.
  3. Subject decodieren, Absender extrahieren.
  4. Wenn Subject (case-insensitive, getrimmt) == 'TEST':
        Antwort an den Absender vormerken (Pro-Lauf-Dedup pro From-Adresse,
        damit Flooding nicht zur Reflection-Schleuder wird).
  5. In jedem Fall die Mail aus dem Postfach loeschen, sofern
     'delete_processed=true' (Default) - sonst kommt dieselbe Mail im
     naechsten Lauf wieder vorbei.

Sicherheitshinweis: Wer 'imap.allow_anyone=true' setzt, sollte sich der
Implikationen bewusst sein. Diese Funktion gibt Anlagenstati an jeden
Absender zurueck, der das richtige Subject trifft.
"""
import imaplib
import logging
from dataclasses import dataclass, field
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class TestRequest:
    """Eine bestaetigte TEST-Anfrage, die beantwortet werden soll."""
    sender: str          # Email-Adresse des Absenders (RFC 5322)
    message_id: str      # Original Message-ID fuer In-Reply-To
    subject: str         # Originales (decodiertes) Subject
    uid: bytes           # IMAP-Sequenz-Nr. der Original-Mail


@dataclass
class InboxResult:
    """Ergebnis eines Inbox-Laufs."""
    test_requests: List[TestRequest] = field(default_factory=list)
    other_count: int = 0       # Mails, die nicht 'TEST' waren
    duplicate_count: int = 0   # zusaetzliche TEST-Mails desselben Absenders im selben Lauf
    error: Optional[str] = None


def _decode_subject(raw: Optional[str]) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw.strip()


def _normalize_subject(s: str) -> str:
    return s.strip().casefold()


def process_inbox(host: str, port: int, use_ssl: bool,
                  username: str, password: str,
                  folder: str = "INBOX",
                  test_subject: str = "TEST",
                  delete_processed: bool = True,
                  dry_run: bool = False,
                  timeout: int = 30) -> InboxResult:
    """Postfach durchgehen.

    Liefert eine Liste von TestRequest-Objekten zurueck (max. eine pro
    Absender) und loescht die verarbeiteten Mails - im Dry-Run werden Mails
    NICHT geloescht, damit ein echter Lauf die TEST-Anfrage anschliessend
    noch sehen kann.
    """
    result = InboxResult()
    target_subject = _normalize_subject(test_subject)
    seen_senders = set()

    M = None
    try:
        if use_ssl:
            M = imaplib.IMAP4_SSL(host, port, timeout=timeout)
        else:
            M = imaplib.IMAP4(host, port, timeout=timeout)
        M.login(username, password)
        typ, _ = M.select(folder)
        if typ != "OK":
            raise RuntimeError(f"IMAP SELECT '{folder}' fehlgeschlagen.")

        typ, data = M.search(None, "ALL")
        if typ != "OK":
            raise RuntimeError("IMAP SEARCH fehlgeschlagen.")

        nums = data[0].split() if data and data[0] else []
        log.info("IMAP: %d Nachricht(en) im Postfach.", len(nums))

        for num in nums:
            typ, msg_data = M.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                log.warning("IMAP FETCH %s schlug fehl, ueberspringe.", num)
                continue
            raw = msg_data[0][1]
            msg = message_from_bytes(raw)

            subject_dec = _decode_subject(msg.get("Subject"))
            from_addr = parseaddr(msg.get("From", ""))[1].strip().lower()
            msg_id = (msg.get("Message-ID") or "").strip()

            is_test = (_normalize_subject(subject_dec) == target_subject)

            if is_test and from_addr:
                if from_addr in seen_senders:
                    result.duplicate_count += 1
                    log.info("IMAP: weitere TEST-Mail von %s im selben Lauf - "
                             "wird stillschweigend geloescht.", from_addr)
                else:
                    seen_senders.add(from_addr)
                    result.test_requests.append(TestRequest(
                        sender=from_addr,
                        message_id=msg_id,
                        subject=subject_dec,
                        uid=num,
                    ))
                    log.info("IMAP: TEST-Anfrage von %s entgegengenommen.",
                             from_addr)
            else:
                result.other_count += 1
                log.info("IMAP: Mail ohne TEST-Subject von '%s' (Subject='%s') "
                         "wird stillschweigend geloescht.",
                         from_addr or "?", subject_dec)

            if delete_processed and not dry_run:
                M.store(num, "+FLAGS", r"(\Deleted)")

        if delete_processed and not dry_run:
            M.expunge()

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        log.error("IMAP-Verarbeitung fehlgeschlagen: %s", result.error)
    finally:
        if M is not None:
            try:
                M.close()
            except Exception:
                pass
            try:
                M.logout()
            except Exception:
                pass

    return result
