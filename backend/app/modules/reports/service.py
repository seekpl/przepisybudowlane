"""Zgłoszenia błędów: przy każdej karcie, z terminem obsługi w dniach roboczych.

RODO: adres e-mail jest opcjonalny i zapisujemy go tylko ze zgodą; po zamknięciu zgłoszenia
usuwamy go po okresie retencji (``purge_expired_emails``, uruchamiane przez worker).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clock import now, today
from app.config import Settings
from app.history import record
from app.models import ErrorReport, LegalUnit, TaskKind
from app.modules.editorial.tasks import ensure_task

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReportError(ValueError):
    pass


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = (h + m - 7 * n + 114) % 31 + 1
    return date(year, month, day)


def public_holidays(year: int) -> set[date]:
    """Dni ustawowo wolne od pracy w Polsce (z Wigilią od 2025 r.)."""
    easter = _easter(year)
    fixed = {(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 25), (12, 26)}
    if year >= 2025:
        fixed.add((12, 24))
    days = {date(year, mo, d) for mo, d in fixed}
    days |= {easter, easter + timedelta(days=1), easter + timedelta(days=49), easter + timedelta(days=60)}
    return days


def add_working_days(start: date, n: int) -> date:
    d = start
    added = 0
    holidays = public_holidays(d.year) | public_holidays(d.year + 1)
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            added += 1
    return d


def create_report(
    s: Session,
    settings: Settings,
    *,
    target_path: str,
    target_label: str | None,
    unit_slug: str | None,
    message: str,
    contact_email: str | None,
    consent: bool,
) -> ErrorReport:
    message = message.strip()
    if len(message) < 5:
        raise ReportError("Opisz krótko, co jest nie tak — wystarczy jedno zdanie.")
    email = (contact_email or "").strip() or None
    if email is not None:
        if not _EMAIL.match(email):
            raise ReportError("Sprawdź adres e-mail albo zostaw pole puste.")
        if not consent:
            raise ReportError("Zaznacz zgodę na użycie adresu albo usuń adres z formularza.")
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == unit_slug)) if unit_slug else None
    report = ErrorReport(
        target_path=target_path[:500],
        target_label=target_label,
        unit_id=unit.id if unit else None,
        message=message,
        contact_email=email,
        consent=bool(email and consent),
        due_on=add_working_days(today(), settings.report_sla_working_days),
    )
    s.add(report)
    s.flush()
    task = ensure_task(
        s,
        kind=TaskKind.ZGLOSZENIE_BLEDU,
        dedupe_key=f"zgloszenie:{report.id}",
        title=f"Zgłoszenie ZB-{report.id}: {target_label or target_path}",
        details={"zgloszenie": report.id, "adres": target_path},
        act_id=unit.act_id if unit else None,
        unit_id=unit.id if unit else None,
        due_on=report.due_on,
    )
    report.task_id = task.id
    record(
        s,
        actor="publiczny",
        entity="error_report",
        entity_id=report.id,
        action="zgloszono",
        adres=target_path,
    )
    return report


def close_report(s: Session, report: ErrorReport, settings: Settings, actor: str) -> None:
    report.state = "zamkniete"
    report.closed_at = now()
    if report.contact_email:
        report.email_purge_after = today() + timedelta(days=settings.report_email_retention_days)
    record(s, actor=actor, entity="error_report", entity_id=report.id, action="zamknieto")


def purge_expired_emails(s: Session) -> int:
    result = s.execute(
        update(ErrorReport)
        .where(
            ErrorReport.email_purge_after.is_not(None),
            ErrorReport.email_purge_after <= today(),
            ErrorReport.contact_email.is_not(None),
        )
        .values(contact_email=None)
    )
    return result.rowcount or 0  # type: ignore[attr-defined]
