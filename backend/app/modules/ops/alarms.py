"""Alarmy źródeł: otwarty alarm wstrzymuje synchronizację i odbiera przepisom status „potwierdzona”."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.history import record
from app.models import SourceAlarm

ELI = "eli"


def open_alarm(s: Session, source: str = ELI) -> SourceAlarm | None:
    return s.scalar(
        select(SourceAlarm)
        .where(SourceAlarm.source == source, SourceAlarm.resolved_at.is_(None))
        .order_by(SourceAlarm.id.desc())
    )


def resolve_alarm(s: Session, alarm: SourceAlarm, *, actor: str, resolution: str) -> None:
    """Reakcja człowieka: po poprawie kontraktu albo potwierdzeniu, że zmiana źródła jest bezpieczna."""
    alarm.resolved_at = now()
    alarm.resolved_by = actor
    alarm.resolution = resolution
    record(
        s, actor=actor, entity="source_alarm", entity_id=alarm.id, action="zamknieto", rozwiazanie=resolution
    )
