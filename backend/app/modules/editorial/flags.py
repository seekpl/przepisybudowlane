from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.history import record
from app.models import ContentFlag


def active_flags(s: Session, entity: str, entity_ids: list[int]) -> dict[int, ContentFlag]:
    if not entity_ids:
        return {}
    rows = s.scalars(
        select(ContentFlag).where(
            ContentFlag.entity == entity,
            ContentFlag.entity_id.in_(entity_ids),
            ContentFlag.resolved_at.is_(None),
        )
    ).all()
    return {f.entity_id: f for f in rows}


def flag_content(s: Session, *, entity: str, entity_id: int, reason: str, actor: str) -> ContentFlag:
    """Zawiesza fragment treści do przeglądu. Drugie zawieszenie tego samego fragmentu nic nie zmienia."""
    current = active_flags(s, entity, [entity_id]).get(entity_id)
    if current is not None:
        return current
    flag = ContentFlag(entity=entity, entity_id=entity_id, reason=reason, created_by=actor)
    s.add(flag)
    s.flush()
    record(s, actor=actor, entity=entity, entity_id=entity_id, action="zawieszono", powod=reason)
    return flag


def resolve_flag(s: Session, flag: ContentFlag, *, actor: str) -> None:
    flag.resolved_at = now()
    flag.resolved_by = actor
    record(s, actor=actor, entity=flag.entity, entity_id=flag.entity_id, action="odwieszono", flaga=flag.id)
