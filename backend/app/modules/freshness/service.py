"""Zbiera z bazy dane do oceny aktualności aktu lub jednostki."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.clock import now, today
from app.config import get_settings
from app.models import (
    DetectedAmendment,
    LegalAct,
    LegalTextVersion,
    LegalUnit,
    LegalUnitVersion,
    LegalValidityInterval,
    SourceVerification,
    SystemHistory,
    TextReview,
)
from app.modules.freshness.engine import (
    Amendment,
    Confirmation,
    Freshness,
    FreshnessInput,
    Interval,
    evaluate,
)
from app.modules.ops.alarms import open_alarm


@dataclass
class UnitText:
    unit_version: LegalUnitVersion | None
    text_version: LegalTextVersion | None
    missing_from: LegalTextVersion | None  # najnowszy tekst, w którym jednostki brak


def current_text(s: Session, act_id: int) -> LegalTextVersion | None:
    return s.scalar(
        select(LegalTextVersion)
        .where(LegalTextVersion.act_id == act_id, LegalTextVersion.review_state == TextReview.ZAAKCEPTOWANY)
        .order_by(LegalTextVersion.recorded_at.desc(), LegalTextVersion.id.desc())
    )


def unit_text(s: Session, unit: LegalUnit) -> UnitText:
    latest = current_text(s, unit.act_id)
    if latest is None:
        return UnitText(None, None, None)
    uv = s.scalar(
        select(LegalUnitVersion).where(
            LegalUnitVersion.unit_id == unit.id, LegalUnitVersion.text_version_id == latest.id
        )
    )
    if uv is not None:
        return UnitText(uv, latest, None)
    # Jednostki nie ma w najnowszym tekście — pokazujemy ostatnie znane brzmienie i mówimy o tym.
    older = s.execute(
        select(LegalUnitVersion, LegalTextVersion)
        .join(LegalTextVersion, LegalTextVersion.id == LegalUnitVersion.text_version_id)
        .where(LegalUnitVersion.unit_id == unit.id, LegalTextVersion.review_state == TextReview.ZAAKCEPTOWANY)
        .order_by(LegalTextVersion.recorded_at.desc(), LegalTextVersion.id.desc())
    ).first()
    if older is None:
        return UnitText(None, None, latest)
    return UnitText(older[0], older[1], latest)


def last_sync_ok(s: Session, act_id: int) -> datetime | None:
    return s.scalar(
        select(func.max(SystemHistory.recorded_at)).where(
            SystemHistory.entity == "legal_act",
            SystemHistory.entity_id == act_id,
            SystemHistory.action == "synchronizacja_ok",
        )
    )


def _verification(s: Session, act_id: int, unit_id: int | None) -> Confirmation | None:
    q = select(SourceVerification).where(SourceVerification.act_id == act_id)
    q = (
        q.where(SourceVerification.unit_id.is_(None))
        if unit_id is None
        else q.where((SourceVerification.unit_id.is_(None)) | (SourceVerification.unit_id == unit_id))
    )
    v = s.scalar(q.order_by(SourceVerification.verified_at.desc()))
    return Confirmation(v.verified_at, v.scope) if v else None


def active_intervals(s: Session, act_id: int, unit_id: int | None) -> list[LegalValidityInterval]:
    newer = aliased(LegalValidityInterval)
    q = select(LegalValidityInterval).where(
        LegalValidityInterval.act_id == act_id,
        ~select(newer.id).where(newer.supersedes_id == LegalValidityInterval.id).exists(),
    )
    q = (
        q.where(LegalValidityInterval.unit_id.is_(None))
        if unit_id is None
        else q.where((LegalValidityInterval.unit_id.is_(None)) | (LegalValidityInterval.unit_id == unit_id))
    )
    return list(s.scalars(q.order_by(LegalValidityInterval.id)))


def amendments(s: Session, act_id: int) -> list[DetectedAmendment]:
    return list(
        s.scalars(
            select(DetectedAmendment)
            .where(DetectedAmendment.act_id == act_id)
            .order_by(DetectedAmendment.published_on)
        )
    )


def _input(
    s: Session, act: LegalAct, text: LegalTextVersion | None, unit_id: int | None, missing_from: str | None
) -> FreshnessInput:
    settings = get_settings()
    return FreshnessInput(
        now=now(),
        today=today(),
        threshold=timedelta(hours=settings.freshness_threshold_hours),
        text_type=text.text_type if text else None,
        legal_status_date=text.legal_status_date if text else None,
        incorporated=frozenset(text.incorporated or []) if text else frozenset(),
        sync_ok=last_sync_ok(s, act.id),
        verification=_verification(s, act.id, unit_id),
        intervals=[
            Interval(iv.kind, iv.valid_from, iv.valid_to, iv.title, iv.description, iv.basis)
            for iv in active_intervals(s, act.id, unit_id)
        ],
        amendments=[
            Amendment(a.amending_eli, a.journal_display, a.published_on, a.entry_into_force)
            for a in amendments(s, act.id)
        ],
        unit_missing_from=missing_from,
        source_paused=_paused_title(s),
        pending_review=_pending_review(s, act.id, text),
    )


def pending_text(s: Session, act_id: int, current: LegalTextVersion | None) -> LegalTextVersion | None:
    """Tekst z ELI czekający na kontrolę człowieka, nowszy niż pokazywany (np. t.j. tylko w PDF)."""
    q = select(LegalTextVersion).where(
        LegalTextVersion.act_id == act_id, LegalTextVersion.review_state == TextReview.DO_KONTROLI
    )
    if current is not None:
        q = q.where(LegalTextVersion.recorded_at >= current.recorded_at, LegalTextVersion.id > current.id)
    return s.scalar(q.order_by(LegalTextVersion.id.desc()))


def _pending_review(s: Session, act_id: int, current: LegalTextVersion | None) -> str | None:
    pending = pending_text(s, act_id, current)
    return pending.journal_display if pending else None


def for_unit(s: Session, unit: LegalUnit, ut: UnitText | None = None) -> Freshness:
    ut = ut or unit_text(s, unit)
    act = s.get(LegalAct, unit.act_id)
    assert act is not None
    missing = ut.missing_from.journal_display if ut.missing_from and ut.unit_version is not None else None
    return evaluate(_input(s, act, ut.text_version, unit.id, missing))


def for_act(s: Session, act: LegalAct) -> Freshness:
    return evaluate(_input(s, act, current_text(s, act.id), None, None))


def _paused_title(s: Session) -> str | None:
    alarm = open_alarm(s)
    return alarm.title if alarm else None
