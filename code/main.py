#!/usr/bin/env python3
# Notlicht-Monitor - Emergency Light Monitoring Tool
# Copyright (C) 2026 Axel Schmidt <axel@schmidtlab.net>
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
Notlicht-Monitor: Hauptprogramm.
Laeuft alle 15 Minuten via systemd-Timer. Entscheidet pro Lauf:
  - Sofort-Alarm bei Uebergang OK -> Stoerung
  - Entwarnung  bei Uebergang Stoerung -> OK
  - Wochenreport am konfigurierten Wochentag/Stunde, genau 1x pro Kalenderwoche
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import load_config
from netlight_client import NetlightClient
from state import State
from mailer import Mailer
import mail_builder


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def should_send_weekly(state: State, cfg: dict, now: datetime,
                       force: bool = False) -> bool:
    if force:
        return True
    weekday = int(cfg["schedule"]["weekly_report_weekday"])
    hour    = int(cfg["schedule"]["weekly_report_hour"])
    if now.isoweekday() != weekday:
        return False
    if now.hour < hour:
        return False
    last = state.last_weekly_report()
    if last is None:
        return True
    # Gleiche ISO-Kalenderwoche? Dann schon gesendet.
    return last.isocalendar()[:2] != now.isocalendar()[:2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/notlicht-monitor/config.yaml")
    parser.add_argument("--secrets", default=None,
                        help="Pfad zu secrets.yaml. Default: neben --config.")
    parser.add_argument("--state",  default="/var/lib/notlicht-monitor/state.json")
    parser.add_argument("--force-weekly", action="store_true",
                        help="Wochenreport jetzt senden (Test).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mails nicht senden, nur auf stdout ausgeben.")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("notlicht-monitor")

    secrets_path = Path(args.secrets) if args.secrets else None
    cfg = load_config(Path(args.config), secrets_path)
    state = State(Path(args.state))
    now = datetime.now().astimezone()

    # --- Geraete abfragen ---
    http_cfg = cfg["http"]
    client = NetlightClient(
        timeout=http_cfg["timeout_seconds"],
        attempts=http_cfg["retry_attempts"],
        delays=http_cfg["retry_delays"],
    )

    snapshots = []
    for dev in cfg["devices"]:
        snap = client.fetch(dev["name"], dev["url"])
        snapshots.append(snap)
        log.info("%s: %s", snap.name, "OK" if snap.is_ok else "STOERUNG")
        if not snap.is_ok:
            for a in snap.abweichungen:
                log.warning("  -> %s", a)

    # --- Mailer ---
    smtp = cfg["smtp"]
    mailer = Mailer(
        host=smtp["host"],
        port=int(smtp["port"]),
        username=smtp.get("username", ""),
        password=smtp.get("password", ""),
        from_address=smtp["from_address"],
        from_name=smtp.get("from_name", smtp["from_address"]),
        use_ssl=bool(smtp.get("use_ssl", True)),
    )
    mail_cfg = cfg["mail"]
    recipients = cfg["recipients"]
    emoji_ok    = mail_cfg["status_emoji_ok"]
    emoji_fault = mail_cfg["status_emoji_fault"]

    def send(subject: str, body: str) -> bool:
        log.info("Versende: %s", subject)
        if args.dry_run:
            print("\n==================== DRY RUN ====================")
            print("An:     ", ", ".join(recipients))
            print("Subject:", subject)
            print("-------------------------------------------------")
            print(body)
            print("==================================================\n")
            return True
        try:
            mailer.send(recipients, subject, body)
            return True
        except Exception as e:
            log.error("Mailversand fehlgeschlagen: %s", e)
            return False

    # --- Alarm/Entwarnung je Geraet (Status-Uebergang) ---
    for snap in snapshots:
        prev = state.was_ok(snap.name)
        now_ok = snap.is_ok
        state.update_device(snap.name, now_ok, now)

        if prev is None:
            # Erster Lauf fuer dieses Geraet: kein Alarm, nur State merken.
            continue

        if prev and not now_ok:
            subject = mail_cfg["alarm_subject"].format(
                status_emoji=emoji_fault,
                device=snap.name,
                date=now.strftime("%d.%m.%Y"),
            )
            body = mail_builder.build_alarm_body(snap, mail_cfg, now)
            send(subject, body)

        elif not prev and now_ok:
            subject = mail_cfg["recovery_subject"].format(
                status_emoji=emoji_ok,
                device=snap.name,
                date=now.strftime("%d.%m.%Y"),
            )
            body = mail_builder.build_recovery_body(snap, mail_cfg, now)
            send(subject, body)

    # --- Wochenreport ---
    if should_send_weekly(state, cfg, now, force=args.force_weekly):
        all_ok = all(s.is_ok for s in snapshots)
        subject = mail_cfg["weekly_subject"].format(
            status_emoji=emoji_ok if all_ok else emoji_fault,
            date=now.strftime("%d.%m.%Y"),
        )
        body = mail_builder.build_weekly_body(snapshots, mail_cfg, now)
        if send(subject, body) and not args.dry_run:
            state.set_weekly_report_sent(now)

    state.save()

    return 0 if all(s.is_ok for s in snapshots) else 1


if __name__ == "__main__":
    sys.exit(main())
