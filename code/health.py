# Notlicht-Monitor - Emergency Light Monitoring Tool
# Copyright (C) 2026 Axel Schmidt
# SPDX-License-Identifier: LicenseRef-Notlicht-Monitor-NC
#
# HAFTUNGSAUSSCHLUSS: Keine Gewaehrleistung. Siehe Hauptprogramm.
"""
Selbstueberwachtung ("Self health"): erkennen, wenn das Monitoring-Orchestrierende
(selbst systemd-Timer oder Laufzyklen) krank wird — nicht nur, wenn eine Anlage
offline ist.

Jeder Lauf produziert strukturierte Logzeilen ueber einen eigenen Logger
('notlicht-health'). Schwere Findings koennen zusaetzlich (rate-limitiert per
Konfiguration) als Mail an die normalen recipients gehen — damit besteht keine
still Zustand wie bei einem eingefrorenen Timer ohne externem Beobachter.

Hinweise zur Architektur (Kurzfassung):
- **Timer/Meta**: systemctl-show auf die Timer-Unit; typischer Fehler unter
  systemd 257: SubState=elapsed + NextElapseUSecMonotonic=infinity ⇒ nie wieder
  geplant.
- **Zwei-Teilnehmer-Sicht auf Lücken**: (a) systemd plant Starte, (b) dieses Tool
  schreibt nach jedem erfolgreichen Durchlauf `monitor_last_finished_iso` im
  State. Widerspruch ⇒ Finding.
- **Betriebssystem-Anker**: State-Verzeichnis schreibbar; systemctl kann fehlen
  (Entwicklung) ⇒ nur Hinweis, kein Crash.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from state import State

log = logging.getLogger("notlicht-health")

_UNIT_SAFE = re.compile(r"^[A-Za-z0-9_.@-]+$")


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str
    detail: str = ""

    def line(self) -> str:
        d = f" | {self.detail}" if self.detail else ""
        return f"code={self.code} severity={self.severity.value} msg={self.message}{d}"


@dataclass
class HealthReport:
    findings: List[Finding] = field(default_factory=list)
    systemctl_stderr: str = ""
    systemd_timer_props: Dict[str, str] = field(default_factory=dict)

    def add(self, sev: Severity, code: str, message: str, detail: str = "") -> None:
        self.findings.append(Finding(sev, code, message, detail))

    @property
    def max_severity(self) -> Severity:
        order = [Severity.INFO, Severity.WARNING, Severity.CRITICAL]
        best = Severity.INFO
        for f in self.findings:
            if order.index(f.severity) > order.index(best):
                best = f.severity
        return best


def _parse_show(output: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _run_systemctl_show(
    systemctl: str, unit: str, timeout: float
) -> tuple[Optional[Dict[str, str]], str]:
    if not _UNIT_SAFE.match(unit):
        return None, "unit name failed safety check"
    try:
        r = subprocess.run(
            [
                systemctl,
                "show",
                unit,
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "UnitFileState",
                "-p",
                "NextElapseUSecMonotonic",
                "-p",
                "NextElapseUSecRealtime",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return None, "systemctl binary not found"
    except subprocess.TimeoutExpired:
        return None, "systemctl show timed out"
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return None, (err or f"systemctl exit {r.returncode}")
    return _parse_show(r.stdout), err


def _analyze_timer_props(props: Dict[str, str], report: HealthReport) -> None:
    active = props.get("ActiveState", "")
    sub = props.get("SubState", "")
    unit_file = props.get("UnitFileState", "")
    next_mono = props.get("NextElapseUSecMonotonic", "")

    detail = (
        f"ActiveState={active} SubState={sub} "
        f"NextElapseUSecMonotonic={next_mono} UnitFileState={unit_file}"
    )

    if unit_file == "masked":
        report.add(
            Severity.CRITICAL,
            "TIMER_MASKED",
            "Timer-Unit ist maskiert — sie wird nie starten.",
            detail,
        )
        return

    if active and active != "active":
        report.add(
            Severity.CRITICAL,
            "TIMER_NOT_ACTIVE",
            f"Timer-Unit ist nicht aktiv (ActiveState={active}).",
            detail,
        )

    if sub == "elapsed" and next_mono in ("infinity", ""):
        report.add(
            Severity.CRITICAL,
            "TIMER_STALLED_NO_NEXT",
            "Timer ist 'elapsed' ohne naechsten monotonen Starttermin — "
            "Monitoring und IMAP-Polling stoppen still.",
            detail,
        )
    elif sub == "elapsed":
        report.add(
            Severity.WARNING,
            "TIMER_SUBSTATE_ELAPSED",
            "Timer SubState=elapsed (pruefen, ob ein naechster Lauf geplant ist).",
            detail,
        )


def _gap_check(
    state: State,
    now: datetime,
    interval_min: int,
    warn_factor: float,
    crit_factor: float,
    report: HealthReport,
) -> None:
    last = state.monitor_last_finished()
    if last is None:
        report.add(
            Severity.INFO,
            "NO_GAP_BASELINE_YET",
            "Kein gespeicherter Referenz-Endzeitpunkt des Monitors "
            "(erster Lauf nach Update oder geleerter State-Datei).",
        )
        return

    delta = now - last
    if delta < timedelta(0):
        report.add(
            Severity.WARNING,
            "CLOCK_JUMP_OR_STATE",
            "Aktuelle Zeit liegt vor gespeicherter monitor_last_finished — "
            "Uhr/Statedatei pruefen.",
            f"now={now.isoformat()} last={last.isoformat()}",
        )
        return

    warn_thr = timedelta(minutes=interval_min * warn_factor)
    crit_thr = timedelta(minutes=interval_min * crit_factor)

    if delta > crit_thr:
        report.add(
            Severity.CRITICAL,
            "MONITOR_GAP_CRITICAL",
            f"Sehr lange keine erfolgreichen Monitor-Laeufe (>{crit_thr}).",
            f"minutes_since_last_finish={delta.total_seconds()/60:.1f} "
            f"critical_threshold_min={crit_thr.total_seconds()/60:.0f}",
        )
    elif delta > warn_thr:
        report.add(
            Severity.WARNING,
            "MONITOR_GAP_WARN",
            f"Zu langer Abstand seit letztem erfolgreichen Monitor-Lauf (>{warn_thr}).",
            f"minutes_since_last_finish={delta.total_seconds()/60:.1f} "
            f"warn_threshold_min={warn_thr.total_seconds()/60:.0f}",
        )


def _state_dir_check(state_path: Path, report: HealthReport) -> None:
    parent = state_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        report.add(
            Severity.CRITICAL,
            "STATE_DIR_CREATABLE",
            f"State-Verzeichnis laesst sich nicht anlegen: {parent}",
            str(e),
        )
        return
    if not os.access(parent, os.W_OK):
        report.add(
            Severity.CRITICAL,
            "STATE_DIR_READONLY",
            f"Keine Schreibberechtigung auf State-Verzeichnis: {parent}",
            "",
        )
        return

    usage = shutil.disk_usage(parent)
    free_mb = usage.free / (1024 * 1024)
    report.add(
        Severity.INFO,
        "DISK_SPACE",
        "Freier Speicherplatz auf dem Volume des State-Verzeichnisses.",
        f"free_MB={free_mb:.1f}",
    )


def collect_startup_health(
    hc: Dict[str, Any],
    state: State,
    state_path: Path,
    now: datetime,
) -> HealthReport:
    report = HealthReport()
    interval = max(1, int(hc.get("expected_interval_minutes", 15)))
    warn_fac = float(hc.get("gap_warning_factor", 2.0))
    crit_fac = float(hc.get("gap_critical_factor", 4.0))

    timer_unit = str(hc.get("timer_unit", "notlicht-monitor.timer"))
    systemctl = str(hc.get("systemctl_bin", "/bin/systemctl"))
    timeout = float(hc.get("systemctl_timeout_seconds", 10))

    _state_dir_check(state_path, report)
    _gap_check(state, now, interval, warn_fac, crit_fac, report)

    props, err = _run_systemctl_show(systemctl, timer_unit, timeout)
    report.systemctl_stderr = err
    if props is None:
        report.add(
            Severity.WARNING,
            "SYSTEMD_QUERY_UNAVAILABLE",
            "systemctl fuer Timer-Check nicht nutzbar (Entwicklungsrechner oder Rechte).",
            err,
        )
    else:
        report.systemd_timer_props = props
        _analyze_timer_props(props, report)

    return report


def augment_imap_streak(
    report: HealthReport,
    hc: Dict[str, Any],
    imap_enabled: bool,
    streak: int,
) -> None:
    if not imap_enabled or streak <= 0:
        return
    w_after = int(hc.get("imap_failure_warning_after", 2))
    c_after = int(hc.get("imap_failure_critical_after", 5))
    if streak >= c_after:
        report.add(
            Severity.CRITICAL,
            "IMAP_FAIL_STREAK_CRITICAL",
            f"IMAP-Fehler in {streak} aufeinanderfolgenden Laeufen "
            f"(>= {c_after}). TEST-Antworten u.U. blockiert.",
            f"streak={streak}",
        )
    elif streak >= w_after:
        report.add(
            Severity.WARNING,
            "IMAP_FAIL_STREAK_WARN",
            f"IMAP-Fehler in {streak} aufeinanderfolgenden Laeufen "
            f"(>= {w_after}).",
            f"streak={streak}",
        )


def log_health_report(report: HealthReport) -> None:
    """Strukturierte Ausgabe: eine Zeile pro Finding + eine Summary-Zeile."""
    counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
    for f in report.findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        if f.severity == Severity.INFO:
            lvl = logging.INFO
        elif f.severity == Severity.CRITICAL:
            lvl = logging.ERROR
        else:
            lvl = logging.WARNING
        log.log(lvl, "FINDING %s", f.line())
    mx = report.max_severity.value
    sum_lvl = logging.INFO
    if report.max_severity == Severity.CRITICAL:
        sum_lvl = logging.ERROR
    elif report.max_severity == Severity.WARNING:
        sum_lvl = logging.WARNING
    log.log(
        sum_lvl,
        "SUMMARY findings=%s max_severity=%s (INFO/WARN/CRIT=%s/%s/%s)%s",
        len(report.findings),
        mx,
        counts["INFO"],
        counts["WARNING"],
        counts["CRITICAL"],
        f" systemd_stderr={report.systemctl_stderr!r}"
        if report.systemctl_stderr
        else "",
    )


def format_health_digest_body(
    report: HealthReport,
    now: datetime,
    mail_cfg: Dict[str, Any],
) -> str:
    host = socket.gethostname()
    lines = [
        "=== Notlicht-Monitor — Selbstueberwachung ===",
        f"Zeitpunkt Lokal: {now.strftime('%d.%m.%Y %H:%M:%S %Z')}",
        f"Host: {host}",
        f"Hoechste Schwere: {report.max_severity.value}",
        "",
        "--- Befunde ---",
    ]
    for f in sorted(
        report.findings,
        key=lambda x: (["INFO", "WARNING", "CRITICAL"].index(x.severity.value), x.code),
    ):
        lines.append(f"[{f.severity.value}] {f.code}: {f.message}")
        if f.detail:
            lines.append(f"    Detail: {f.detail}")
    if report.systemd_timer_props:
        lines.extend(
            (
                "",
                "--- systemd Timer (roh) ---",
                "\n".join(f"{k}={v}" for k, v in sorted(report.systemd_timer_props.items())),
            )
        )

    footer = mail_cfg.get("custom_footer") or ""
    footer = footer.strip()
    lines.extend(
        (
            "",
            "--- Was tun? ---",
            "- Timer-Fehler (LISTEN stalled / kein NEXT): "
            "`sudo systemctl daemon-reload && sudo systemctl restart "
            "notlicht-monitor.timer` dann `systemctl list-timers`.",
            "- Grosse Lücken ohne Timer-Fehler: Pi-Anlaufzeit, Strom,"
            "`systemctl`-Status oder State-Datei pruefen.",
            "- Bei IMAP-Streaks: Zugangsdaten/Webhoster-Quota/Firewall pruefen.",
        )
    )
    if footer:
        lines.extend(("", "---", footer))
    return "\n".join(lines)


def maybe_send_health_alert(
    hc: Dict[str, Any],
    report: HealthReport,
    *,
    mail_cfg: Dict[str, Any],
    send_func: Callable[[str, str], bool],
    state: State,
    now: datetime,
    dry_run: bool,
) -> None:
    if not hc.get("enabled", True):
        return
    if not hc.get("alert_on_findings", True):
        log.info("SUMMARY Mail-Unterdrueckung: health.alert_on_findings=false")
        return

    need_mail = False
    if report.max_severity == Severity.CRITICAL and hc.get("alert_critical", True):
        need_mail = True
    elif report.max_severity == Severity.WARNING and hc.get("alert_warning", False):
        need_mail = True
    # INFO-only: never mail unless override
    if not need_mail:
        return

    cool_h = float(hc.get("alert_cooldown_hours", 24))
    last = state.health_last_alert_sent()
    if last is not None and (now - last) < timedelta(hours=cool_h):
        log.info(
            "Health-Mail unterdrueckt (Cooldown): letzte=%s cooldown_h=%s",
            last.isoformat(),
            cool_h,
        )
        return

    sev = report.max_severity.value
    if sev == "CRITICAL":
        emoji = mail_cfg.get("health_emoji_critical", mail_cfg.get("status_emoji_fault", "!!"))
    else:
        emoji = mail_cfg.get("health_emoji_warn", "!!")

    subject_tmpl = mail_cfg.get(
        "health_subject",
        "{severity_emoji} Selbstueberwachung Notlicht-Monitor [{severity}] ({hostname})",
    )
    subject = subject_tmpl.format(
        severity_emoji=emoji,
        severity=sev,
        hostname=socket.gethostname(),
        date=now.strftime("%d.%m.%Y"),
    )
    body = format_health_digest_body(report, now, mail_cfg)
    log.info("Versende Health-Digest per Mail (severity=%s)", sev)
    if dry_run:
        print("\n================== DRY RUN: HEALTH ==================")
        print("Subject:", subject)
        print("-----------------------------------------------------")
        print(body)
        print("=====================================================\n")
        return

    ok = send_func(subject, body)
    if ok:
        state.set_health_alert_sent(now)
