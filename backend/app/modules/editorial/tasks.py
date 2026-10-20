from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.history import record
from app.models import EditorialTask


def ensure_task(
    s: Session,
    *,
    kind: str,
    dedupe_key: str,
    title: str,
    details: dict[str, Any] | None = None,
    act_id: int | None = None,
    unit_id: int | None = None,
    due_on: date | None = None,
) -> EditorialTask:
    """Tworzy zadanie redakcyjne albo zwraca istniejące o tym samym kluczu — ponowiona synchronizacja nie dubluje zadań."""
    existing = s.scalar(select(EditorialTask).where(EditorialTask.dedupe_key == dedupe_key))
    if existing is not None:
        return existing
    task = EditorialTask(
        kind=kind,
        dedupe_key=dedupe_key,
        title=title,
        details=details or {},
        act_id=act_id,
        unit_id=unit_id,
        due_on=due_on,
    )
    s.add(task)
    s.flush()
    record(s, actor="system", entity="editorial_task", entity_id=task.id, action="utworzono", rodzaj=kind)
    return task
