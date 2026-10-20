from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import SystemHistory


def record(
    session: Session, *, actor: str, entity: str, entity_id: int | None, action: str, **data: Any
) -> None:
    """Dopisuje wpis do dziennika systemowego. Nigdy nie aktualizuje ani nie usuwa starszych."""
    session.add(SystemHistory(actor=actor, entity=entity, entity_id=entity_id, action=action, data=data))
