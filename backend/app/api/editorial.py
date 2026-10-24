"""API redakcji. Uwierzytelnianie tokenem do czasu wdrożenia OIDC (plan: po ustaleniu modelu kont)."""

from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.config import Editor, Settings, get_settings
from app.db import get_session
from app.history import record
from app.models import (
    EditorialEvent,
    EditorialState,
    EditorialTask,
    ErrorReport,
    Explanation,
    ExplanationVersion,
    LegalAct,
    LegalTextVersion,
    LegalUnit,
    LegalValidityInterval,
    SearchMiss,
    SearchSynonym,
    SourceAlarm,
    TextReview,
    ValidityKind,
)
from app.modules.editorial.workflow import ENTITY_MODELS, WorkflowError, entity_name, transition
from app.modules.freshness.service import current_text, unit_text
from app.modules.ops.alarms import resolve_alarm
from app.modules.reports.service import close_report
from app.modules.search.misses import proposals
from app.modules.search.service import rebuild_index
from app.modules.sync.service import diff_units

router = APIRouter(prefix="/api/v1/redakcja", tags=["redakcja"])


def current_editor(
    authorization: str | None = Header(default=None), settings: Settings = Depends(get_settings)
) -> Editor:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token:
        for editor in settings.editors():
            if secrets.compare_digest(editor.token, token):
                return editor
    raise HTTPException(401, "Zaloguj się tokenem redakcji.")


class EditorOut(BaseModel):
    name: str
    roles: list[str]


class TaskOut(BaseModel):
    id: int
    kind: str
    title: str
    details: dict[str, Any]
    state: str
    created_at: datetime
    due_on: date | None
    act: str | None
    unit: str | None
    act_slug: str | None = None


class CloseIn(BaseModel):
    resolution: str = Field(min_length=3, max_length=2000)


class ContentOut(BaseModel):
    entity: str
    id: int
    label: str
    version_no: int
    state: str
    author: str
    reviewer: str | None
    is_demo: bool
    created_at: datetime
    published_at: datetime | None


class TransitionIn(BaseModel):
    to_state: EditorialState
    comment: str | None = Field(default=None, max_length=2000)


class EventOut(BaseModel):
    from_state: str | None
    to_state: str
    actor: str
    comment: str | None
    created_at: datetime


class DraftIn(BaseModel):
    unit_slug: str
    title: str | None = Field(default="Co to znaczy w praktyce", max_length=200)
    body: str = Field(min_length=10, max_length=20000)


class TextDecisionIn(BaseModel):
    accept: bool
    comment: str = Field(min_length=3, max_length=2000)


class ReportAdminOut(BaseModel):
    number: str
    target_path: str
    target_label: str | None
    message: str
    has_email: bool
    state: str
    created_at: datetime
    due_on: date


@router.get("/ja", response_model=EditorOut)
def me(editor: Editor = Depends(current_editor)) -> EditorOut:
    return EditorOut(name=editor.name, roles=sorted(editor.roles))


@router.get("/zadania", response_model=list[TaskOut])
def tasks(
    stan: str = "otwarte", s: Session = Depends(get_session), _: Editor = Depends(current_editor)
) -> list[TaskOut]:
    rows = s.scalars(
        select(EditorialTask)
        .where(EditorialTask.state == stan)
        .order_by(EditorialTask.due_on.nulls_last(), EditorialTask.id)
    ).all()
    out = []
    for t in rows:
        act = s.get(LegalAct, t.act_id) if t.act_id else None
        unit = s.get(LegalUnit, t.unit_id) if t.unit_id else None
        out.append(
            TaskOut(
                id=t.id,
                kind=t.kind,
                title=t.title,
                details=t.details or {},
                state=t.state,
                created_at=t.created_at,
                due_on=t.due_on,
                act=act.short_title if act else None,
                unit=unit.slug if unit else None,
                act_slug=act.slug if act else None,
            )
        )
    return out


@router.post("/zadania/{task_id}/zamknij", response_model=TaskOut)
def close_task(
    task_id: int,
    body: CloseIn,
    s: Session = Depends(get_session),
    editor: Editor = Depends(current_editor),
    settings: Settings = Depends(get_settings),
) -> TaskOut:
    t = s.get(EditorialTask, task_id)
    if t is None:
        raise HTTPException(404, "Nie ma takiego zadania.")
    t.state, t.closed_at, t.closed_by, t.resolution = "zamkniete", now(), editor.name, body.resolution
    record(
        s,
        actor=editor.name,
        entity="editorial_task",
        entity_id=t.id,
        action="zamknieto",
        rozwiazanie=body.resolution,
    )
    report = s.scalar(select(ErrorReport).where(ErrorReport.task_id == t.id))
    if report is not None:
        close_report(s, report, settings, editor.name)
    s.commit()
    return TaskOut(
        id=t.id,
        kind=t.kind,
        title=t.title,
        details=t.details or {},
        state=t.state,
        created_at=t.created_at,
        due_on=t.due_on,
        act=None,
        unit=None,
    )


def _label(s: Session, entity: str, v: Any) -> str:
    if entity == "explanation_version":
        e = s.get(Explanation, v.explanation_id)
        unit = s.get(LegalUnit, e.unit_id) if e else None
        return f"Objaśnienie: {unit.title or unit.label}" if unit else "Objaśnienie"
    if entity == "glossary_term_version":
        return f"Pojęcie: {v.term_label}"
    if entity == "guide_version":
        return f"Ścieżka: {v.title}"
    return f"Kreator: {v.title}"


@router.get("/tresci", response_model=list[ContentOut])
def contents(
    stan: EditorialState | None = None, s: Session = Depends(get_session), _: Editor = Depends(current_editor)
) -> list[ContentOut]:
    out = []
    for entity, model in ENTITY_MODELS.items():
        q = select(model)
        if stan is not None:
            q = q.where(model.state == stan)
        for v in s.scalars(q.order_by(model.id)):
            out.append(
                ContentOut(
                    entity=entity,
                    id=v.id,
                    label=_label(s, entity, v),
                    version_no=v.version_no,
                    state=v.state,
                    author=v.author,
                    reviewer=v.reviewer,
                    is_demo=v.is_demo,
                    created_at=v.created_at,
                    published_at=v.published_at,
                )
            )
    return out


@router.post("/tresci/{entity}/{version_id}/przejscie", response_model=ContentOut)
def change_state(
    entity: str,
    version_id: int,
    body: TransitionIn,
    s: Session = Depends(get_session),
    editor: Editor = Depends(current_editor),
) -> ContentOut:
    model = ENTITY_MODELS.get(entity)
    v = s.get(model, version_id) if model else None
    if v is None:
        raise HTTPException(404, "Nie ma takiej wersji treści.")
    try:
        transition(s, v, body.to_state, editor, body.comment)
    except WorkflowError as exc:
        raise HTTPException(409, str(exc)) from exc
    if body.to_state in (EditorialState.OPUBLIKOWANY, EditorialState.ZAWIESZONY, EditorialState.COFNIETY):
        rebuild_index(s)
    s.commit()
    return ContentOut(
        entity=entity,
        id=v.id,
        label=_label(s, entity, v),
        version_no=v.version_no,
        state=v.state,
        author=v.author,
        reviewer=v.reviewer,
        is_demo=v.is_demo,
        created_at=v.created_at,
        published_at=v.published_at,
    )


@router.get("/tresci/{entity}/{version_id}/historia", response_model=list[EventOut])
def history(
    entity: str, version_id: int, s: Session = Depends(get_session), _: Editor = Depends(current_editor)
) -> list[EventOut]:
    rows = s.scalars(
        select(EditorialEvent)
        .where(EditorialEvent.entity == entity, EditorialEvent.entity_id == version_id)
        .order_by(EditorialEvent.id)
    ).all()
    return [
        EventOut(
            from_state=e.from_state,
            to_state=e.to_state,
            actor=e.actor,
            comment=e.comment,
            created_at=e.created_at,
        )
        for e in rows
    ]


@router.post(
    "/objasnienia",
    response_model=ContentOut,
    status_code=201,
    summary="Nowy szkic objaśnienia do bieżącego brzmienia",
)
def new_explanation(
    body: DraftIn, s: Session = Depends(get_session), editor: Editor = Depends(current_editor)
) -> ContentOut:
    if not editor.can("redaktor"):
        raise HTTPException(403, "Objaśnienia pisze redaktor.")
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == body.unit_slug))
    if unit is None:
        raise HTTPException(404, "Nie znaleźliśmy takiego przepisu.")
    ut = unit_text(s, unit)
    if ut.unit_version is None:
        raise HTTPException(409, "Ten przepis nie ma jeszcze zaakceptowanego tekstu.")
    explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    if explanation is None:
        explanation = Explanation(unit_id=unit.id)
        s.add(explanation)
        s.flush()
    no = max((v.version_no for v in explanation.versions), default=0) + 1
    v = ExplanationVersion(
        explanation_id=explanation.id,
        version_no=no,
        title=body.title,
        body=body.body.strip(),
        author=editor.name,
        based_on_unit_version_id=ut.unit_version.id,
    )
    s.add(v)
    s.flush()
    s.add(
        EditorialEvent(
            entity=entity_name(v),
            entity_id=v.id,
            from_state=None,
            to_state=EditorialState.SZKIC,
            actor=editor.name,
        )
    )
    s.commit()
    return ContentOut(
        entity="explanation_version",
        id=v.id,
        label=_label(s, "explanation_version", v),
        version_no=v.version_no,
        state=v.state,
        author=v.author,
        reviewer=None,
        is_demo=False,
        created_at=v.created_at,
        published_at=None,
    )


@router.get("/teksty", summary="Wersje tekstu czekające na kontrolę człowieka (PDF, niska jakość parsera)")
def texts_to_review(
    s: Session = Depends(get_session), _: Editor = Depends(current_editor)
) -> list[dict[str, Any]]:
    rows = s.scalars(
        select(LegalTextVersion)
        .where(LegalTextVersion.review_state == TextReview.DO_KONTROLI)
        .order_by(LegalTextVersion.id)
    ).all()
    return [
        {
            "id": t.id,
            "akt": t.act.short_title,
            "publikator": t.journal_display,
            "jakosc": t.parse_quality,
            "uwagi": t.note,
        }
        for t in rows
    ]


@router.post("/teksty/{text_id}/decyzja")
def decide_text(
    text_id: int,
    body: TextDecisionIn,
    s: Session = Depends(get_session),
    editor: Editor = Depends(current_editor),
) -> dict[str, Any]:
    if not editor.can("recenzent"):
        raise HTTPException(403, "O tekście urzędowym decyduje recenzent.")
    t = s.get(LegalTextVersion, text_id)
    if t is None or t.review_state != TextReview.DO_KONTROLI:
        raise HTTPException(409, "Ta wersja tekstu nie czeka na kontrolę.")
    previous = current_text(s, t.act_id)
    t.review_state = TextReview.ZAAKCEPTOWANY if body.accept else TextReview.ODRZUCONY
    t.reviewed_by, t.reviewed_at = editor.name, now()
    record(
        s,
        actor=editor.name,
        entity="legal_text_version",
        entity_id=t.id,
        action=t.review_state,
        komentarz=body.comment,
    )
    changed = 0
    if body.accept:
        s.flush()
        becomes_current = current_text(s, t.act_id) is t
        if previous is not None and becomes_current:
            # Przyjęty tekst zastępuje poprzedni: zmienione jednostki zawieszają objaśnienia i węzły kreatora.
            changed = diff_units(s, t.act, previous, t)
        rebuild_index(s)
    s.commit()
    return {"id": t.id, "stan": t.review_state, "zmienione_jednostki": changed}


@router.get("/zgloszenia", response_model=list[ReportAdminOut])
def reports(s: Session = Depends(get_session), _: Editor = Depends(current_editor)) -> list[ReportAdminOut]:
    rows = s.scalars(select(ErrorReport).order_by(ErrorReport.id.desc()).limit(200)).all()
    return [
        ReportAdminOut(
            number=f"ZB-{r.id}",
            target_path=r.target_path,
            target_label=r.target_label,
            message=r.message,
            has_email=bool(r.contact_email),
            state=r.state,
            created_at=r.created_at,
            due_on=r.due_on,
        )
        for r in rows
    ]


class AlarmAdminOut(BaseModel):
    id: int
    source: str
    kind: str
    title: str
    details: dict[str, Any]
    raised_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution: str | None


def _alarm_out(a: SourceAlarm) -> AlarmAdminOut:
    return AlarmAdminOut(
        id=a.id,
        source=a.source,
        kind=a.kind,
        title=a.title,
        details=a.details or {},
        raised_at=a.raised_at,
        resolved_at=a.resolved_at,
        resolved_by=a.resolved_by,
        resolution=a.resolution,
    )


@router.get(
    "/alarmy", response_model=list[AlarmAdminOut], summary="Alarmy źródeł (otwarte i ostatnie zamknięte)"
)
def alarms(s: Session = Depends(get_session), _: Editor = Depends(current_editor)) -> list[AlarmAdminOut]:
    rows = s.scalars(
        select(SourceAlarm).order_by(SourceAlarm.resolved_at.nulls_first(), SourceAlarm.id.desc()).limit(50)
    )
    return [_alarm_out(a) for a in rows]


@router.post(
    "/alarmy/{alarm_id}/zamknij",
    response_model=AlarmAdminOut,
    summary="Reakcja na alarm — wznawia synchronizację",
)
def close_alarm(
    alarm_id: int, body: CloseIn, s: Session = Depends(get_session), editor: Editor = Depends(current_editor)
) -> AlarmAdminOut:
    alarm = s.get(SourceAlarm, alarm_id)
    if alarm is None or alarm.resolved_at is not None:
        raise HTTPException(409, "Ten alarm nie jest otwarty.")
    resolve_alarm(s, alarm, actor=editor.name, resolution=body.resolution)
    s.commit()
    return _alarm_out(alarm)


# --- Stosowanie przejściowe aktu uchylonego (arkusz, działanie 2.4) ---------------------------------


class TransitionalIn(BaseModel):
    valid_from: date
    valid_to: date | None = None
    basis: str = Field(min_length=3, max_length=500, description="Przepis przejściowy, np. art. 66 ust. 1 …")
    title: str | None = Field(default=None, max_length=200)
    description: str = Field(
        min_length=10, max_length=2000, description="Do jakich spraw stosuje się akt dalej"
    )
    task_id: int | None = Field(
        default=None, description="Zadanie „przepisy przejściowe”, które ta decyzja zamyka"
    )


class ValidityOut(BaseModel):
    id: int
    kind: str
    valid_from: date | None
    valid_to: date | None
    basis: str | None
    title: str | None
    description: str | None
    recorded_by: str


@router.post(
    "/akty/{slug}/stosowanie-przejsciowe",
    response_model=ValidityOut,
    status_code=201,
    summary="Decyzja człowieka: akt uchylony stosuje się dalej przejściowo (ocena przepisów przejściowych)",
)
def record_transitional(
    slug: str,
    body: TransitionalIn,
    s: Session = Depends(get_session),
    editor: Editor = Depends(current_editor),
) -> ValidityOut:
    if not editor.can("recenzent"):
        raise HTTPException(403, "O stosowaniu przepisów po utracie mocy decyduje recenzent.")
    act = s.scalar(select(LegalAct).where(LegalAct.slug == slug))
    if act is None:
        raise HTTPException(404, "Nie znaleźliśmy takiego aktu.")
    if body.valid_to is not None and body.valid_to < body.valid_from:
        raise HTTPException(422, "Koniec stosowania nie może być wcześniejszy niż początek.")
    interval = LegalValidityInterval(
        act_id=act.id,
        kind=ValidityKind.STOSOWANY_PRZEJSCIOWO,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        basis=body.basis,
        title=body.title,
        description=body.description,
        source="redakcja",
        recorded_by=editor.name,
    )
    s.add(interval)
    s.flush()
    record(
        s,
        actor=editor.name,
        entity="legal_validity_interval",
        entity_id=interval.id,
        action="stosowanie_przejsciowe",
    )
    if body.task_id is not None:
        task = s.get(EditorialTask, body.task_id)
        if task is not None and task.act_id == act.id and task.state == "otwarte":
            task.state, task.closed_at, task.closed_by = "zamkniete", now(), editor.name
            task.resolution = f"Stosowanie przejściowe: {body.basis}"
            record(s, actor=editor.name, entity="editorial_task", entity_id=task.id, action="zamknieto")
    s.commit()
    return ValidityOut(
        id=interval.id,
        kind=interval.kind,
        valid_from=interval.valid_from,
        valid_to=interval.valid_to,
        basis=interval.basis,
        title=interval.title,
        description=interval.description,
        recorded_by=interval.recorded_by,
    )


# --- Propozycje synonimów z zapytań bez wyników (arkusz, działanie 5.4) ------------------------------


class SynonymIn(BaseModel):
    term: str = Field(min_length=2, max_length=80)
    expansions: list[str] = Field(min_length=1, max_length=10)
    miss_id: int | None = None


@router.get("/propozycje-synonimow", summary="Zapytania bez wyników z podpowiedziami słów z indeksu")
def synonym_proposals(
    s: Session = Depends(get_session), _: Editor = Depends(current_editor)
) -> list[dict[str, Any]]:
    return proposals(s)


@router.post("/synonimy", status_code=201, summary="Dodaj synonim do jawnego słownika wyszukiwarki")
def add_synonym(
    body: SynonymIn, s: Session = Depends(get_session), editor: Editor = Depends(current_editor)
) -> dict[str, Any]:
    term = " ".join(body.term.lower().split())
    expansions = [e.strip() for e in body.expansions if e.strip()]
    if not expansions:
        raise HTTPException(422, "Podaj co najmniej jedno słowo, którego ma szukać wyszukiwarka.")
    if s.scalar(select(SearchSynonym).where(SearchSynonym.term == term)) is not None:
        raise HTTPException(409, "Ten synonim już jest w słowniku.")
    syn = SearchSynonym(
        term=term, expansions=expansions, note=f"Dodane przez {editor.name} z zapytań bez wyników"
    )
    s.add(syn)
    if body.miss_id is not None and (miss := s.get(SearchMiss, body.miss_id)) is not None:
        miss.resolved = "synonim"
    s.flush()
    record(s, actor=editor.name, entity="search_synonym", entity_id=syn.id, action="dodano", term=term)
    s.commit()
    return {"term": syn.term, "expansions": syn.expansions}


@router.post(
    "/propozycje-synonimow/{miss_id}/odrzuc", summary="Odrzuć propozycję (zapytanie nie potrzebuje synonimu)"
)
def dismiss_proposal(
    miss_id: int, s: Session = Depends(get_session), editor: Editor = Depends(current_editor)
) -> dict[str, Any]:
    miss = s.get(SearchMiss, miss_id)
    if miss is None:
        raise HTTPException(404, "Nie ma takiej propozycji.")
    miss.resolved = "odrzucone"
    record(s, actor=editor.name, entity="search_miss", entity_id=miss.id, action="odrzucono")
    s.commit()
    return {"id": miss.id, "stan": miss.resolved}
