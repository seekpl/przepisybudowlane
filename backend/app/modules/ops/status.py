"""Panel stanu danych: ostatnia udana synchronizacja, wiek danych, błędy i zaległe zadania."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import schemas as o
from app.clock import now
from app.config import Settings
from app.models import EditorialTask, LegalAct, SourceFetch, SyncCheckpoint, SyncRun
from app.modules.freshness import service as fresh


def status(s: Session, settings: Settings) -> o.StatusOut:
    checkpoint = s.get(SyncCheckpoint, "eli")
    runs = s.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(10)).all()
    acts = []
    for act in s.scalars(select(LegalAct).order_by(LegalAct.id)):
        last = fresh.last_sync_ok(s, act.id)
        tv = fresh.current_text(s, act.id)
        acts.append(
            o.ActStatusOut(
                slug=act.slug,
                short_title=act.short_title,
                last_sync_ok=last,
                data_age_hours=round((now() - last).total_seconds() / 3600, 1) if last else None,
                freshness=o.as_status(fresh.for_act(s, act).status),
                text_type=o.as_text_type(tv.text_type) if tv else None,
                journal=tv.journal_display if tv else None,
            )
        )
    open_tasks = dict(
        s.execute(
            select(EditorialTask.kind, func.count())
            .where(EditorialTask.state == "otwarte")
            .group_by(EditorialTask.kind)
        ).all()
    )
    errors = s.scalars(
        select(SourceFetch).where(SourceFetch.ok.is_(False)).order_by(SourceFetch.id.desc()).limit(10)
    ).all()
    return o.StatusOut(
        generated_at=now(),
        threshold_hours=settings.freshness_threshold_hours,
        last_success_at=checkpoint.last_success_at if checkpoint else None,
        runs=[
            o.RunOut(
                id=r.id,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                trigger=r.trigger,
                stats=r.stats or {},
                errors=r.errors or [],
            )
            for r in runs
        ],
        acts=acts,
        open_tasks={str(k): int(v) for k, v in open_tasks.items()},
        recent_fetch_errors=[
            {"czas": e.fetched_at.isoformat(), "adres": e.url, "rodzaj": e.kind, "blad": e.error}
            for e in errors
        ],
        demo_content=settings.demo_content,
    )
