"""Zadania „szkic AI”, kolejka recenzenta i decyzja (arkusz, działania 3.3, 3.5, 3.6).

Przebieg: zmiana brzmienia zawiesza opublikowane objaśnienie i tworzy zadanie (albo zleca je redaktor) →
worker pisze szkic z Claude → walidatory odrzucają zdania bez pokrycia w tekście → szkic czeka w recenzji →
recenzent widzi różnice i zatwierdza (publikacja z jego nazwiskiem) albo odrzuca. Autorem szkicu jest
„szkic-ai”, więc reguła „autor nie zatwierdza własnej treści” wymusza człowieka przy publikacji.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.config import Editor, Settings
from app.history import record
from app.models import (
    EditorialEvent,
    EditorialState,
    EditorialTask,
    Explanation,
    ExplanationVersion,
    LegalUnit,
    LegalUnitVersion,
    TaskKind,
)
from app.modules.drafting import claude, diff, validators
from app.modules.drafting.sources import fragments
from app.modules.editorial.tasks import ensure_task
from app.modules.editorial.workflow import public_version, transition
from app.modules.freshness.service import unit_text

log = logging.getLogger("przepisy.szkice")

AI_AUTHOR = "szkic-ai"
AI_EDITOR = Editor(name=AI_AUTHOR, roles=frozenset({"redaktor"}), token="")
DEFAULT_TITLE = "Co to znaczy w praktyce"
MAX_ATTEMPTS = 3
OPEN = "otwarte"


def request_draft(s: Session, unit: LegalUnit, *, reason: str, requested_by: str) -> EditorialTask | None:
    """Zadanie „szkic AI” dla bieżącego brzmienia jednostki; jedno na brzmienie (ponowienie nie dubluje)."""
    ut = unit_text(s, unit)
    if ut.unit_version is None or ut.missing_from is not None:
        return None
    return ensure_task(
        s,
        kind=TaskKind.SZKIC_AI,
        dedupe_key=f"szkic-ai:{unit.id}:{ut.unit_version.id}",
        title=f"Szkic AI objaśnienia: {unit.act.short_title}, {unit.label}",
        details={"brzmienie": ut.unit_version.id, "powod": reason, "zlecil": requested_by},
        act_id=unit.act_id,
        unit_id=unit.id,
    )


def _close(s: Session, task: EditorialTask, resolution: str) -> None:
    task.state, task.closed_at, task.closed_by, task.resolution = "zamkniete", now(), AI_AUTHOR, resolution
    record(
        s,
        actor=AI_AUTHOR,
        entity="editorial_task",
        entity_id=task.id,
        action="zamknieto",
        rozwiazanie=resolution,
    )


def _sentence_out(x: validators.Sentence, by_id: dict[str, Any]) -> dict[str, Any]:
    return {
        "tekst": x.text,
        "cytaty": [
            {
                "akapit": q.fragment_id,
                "przepis": by_id[q.fragment_id].label if q.fragment_id in by_id else None,
                "cytat": q.text,
            }
            for q in x.quotes
        ],
    }


def run_task(s: Session, task: EditorialTask, client: Any, settings: Settings) -> ExplanationVersion | None:
    unit = s.get(LegalUnit, task.unit_id) if task.unit_id else None
    if unit is None:
        _close(s, task, "Zadanie nie wskazuje przepisu.")
        return None
    ut = unit_text(s, unit)
    if ut.unit_version is None or ut.missing_from is not None:
        _close(s, task, "Przepis nie ma bieżącego brzmienia w tekście z ELI — szkic nie jest potrzebny.")
        return None
    current = ut.unit_version
    if current.id != task.details.get("brzmienie"):
        # Od zlecenia przyszło nowsze brzmienie: piszemy do niego, a nie do nieaktualnego.
        request_draft(s, unit, reason=task.details.get("powod", ""), requested_by=AI_AUTHOR)
        _close(s, task, "Przyszło nowsze brzmienie przepisu — szkic powstanie w nowym zadaniu.")
        return None

    explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    previous = public_version(explanation.versions) if explanation else None
    old_unit = (
        s.get(LegalUnitVersion, previous.based_on_unit_version_id)
        if previous and previous.based_on_unit_version_id not in (None, current.id)
        else None
    )
    sources = fragments(unit.unit_key, current.content)
    message = claude.user_message(
        unit.label,
        unit.act.title,
        sources,
        previous=previous.body if previous else None,
        old_fragments=fragments(unit.unit_key, old_unit.content) if old_unit else None,
    )
    try:
        result = claude.draft(client, model=settings.ai_model, effort=settings.ai_effort, message=message)
    except claude.DraftError as exc:
        attempts = int(task.details.get("proby", 0)) + 1
        task.details = {**task.details, "proby": attempts, "ostatni_blad": str(exc)}
        log.warning("Szkic AI dla %s nie powstał (próba %s): %s", unit.label, attempts, exc)
        if attempts >= MAX_ATTEMPTS:
            _close(
                s, task, f"Szkic AI nie powstał po {attempts} próbach ({exc}). Objaśnienie napisze redaktor."
            )
        return None

    by_id = {f.id: f for f in sources}
    checked = [validators.check(p, sources) for p in result.paragraphs]
    kept = [[x for x in p if x.ok] for p in checked]
    kept = [p for p in kept if p]
    report: dict[str, Any] = {
        "zadanie": task.id,
        "poprzednia_wersja": previous.id if previous else None,
        "poprzednie_brzmienie": old_unit.id if old_unit else None,
        "przyjete": sum(len(p) for p in kept),
        "odrzucone": [{**_sentence_out(x, by_id), "bledy": x.errors} for p in checked for x in p if not x.ok],
        "uwagi": result.notes,
    }
    if not kept:
        task.details = {**task.details, "raport": report}
        _close(s, task, "Walidatory odrzuciły wszystkie zdania szkicu AI. Objaśnienie napisze redaktor.")
        return None

    if explanation is None:
        explanation = Explanation(unit_id=unit.id)
        s.add(explanation)
        s.flush()
    version = ExplanationVersion(
        explanation_id=explanation.id,
        version_no=max((v.version_no for v in explanation.versions), default=0) + 1,
        title=previous.title if previous and previous.title else DEFAULT_TITLE,
        body="\n\n".join(" ".join(x.text for x in p) for p in kept),
        author=AI_AUTHOR,
        based_on_unit_version_id=current.id,
        ai_model=result.model,
        ai_sentences=[[_sentence_out(x, by_id) for x in p] for p in kept],
        ai_report=report,
    )
    s.add(version)
    s.flush()
    s.add(
        EditorialEvent(
            entity="explanation_version",
            entity_id=version.id,
            from_state=None,
            to_state=EditorialState.SZKIC,
            actor=AI_AUTHOR,
            comment=f"Szkic AI ({result.model}) z {current.text_version.journal_display}",
        )
    )
    transition(s, version, EditorialState.RECENZJA, AI_EDITOR, "Szkic AI po walidacji — czeka na recenzenta.")
    _close(s, task, f"Szkic wersji {version.version_no} czeka w kolejce recenzji.")
    return version


def process_open(s: Session, client: Any, settings: Settings, limit: int = 20) -> list[ExplanationVersion]:
    """Otwarte zadania „szkic AI” po kolei; zapis po każdym, bo wywołanie modelu trwa."""
    tasks = s.scalars(
        select(EditorialTask)
        .where(EditorialTask.kind == TaskKind.SZKIC_AI, EditorialTask.state == OPEN)
        .order_by(EditorialTask.id)
        .limit(limit)
    ).all()
    made = []
    for task in tasks:
        version = run_task(s, task, client, settings)
        s.commit()
        if version is not None:
            made.append(version)
    return made


# --- Kolejka recenzenta (3.6) ----------------------------------------------------------------


def queue(s: Session) -> list[dict[str, Any]]:
    rows = s.scalars(
        select(ExplanationVersion)
        .where(ExplanationVersion.state == EditorialState.RECENZJA, ExplanationVersion.ai_model.is_not(None))
        .order_by(ExplanationVersion.id)
    ).all()
    return [review_item(s, v) for v in rows]


def review_item(s: Session, v: ExplanationVersion) -> dict[str, Any]:
    explanation = s.get(Explanation, v.explanation_id)
    assert explanation is not None
    unit = s.get(LegalUnit, explanation.unit_id)
    assert unit is not None
    report = v.ai_report or {}
    previous = (
        s.get(ExplanationVersion, report["poprzednia_wersja"]) if report.get("poprzednia_wersja") else None
    )
    old_unit = (
        s.get(LegalUnitVersion, report["poprzednie_brzmienie"])
        if report.get("poprzednie_brzmienie")
        else None
    )
    new_unit = s.get(LegalUnitVersion, v.based_on_unit_version_id) if v.based_on_unit_version_id else None
    new_sentences = [x for p in (v.ai_sentences or []) for x in p]
    return {
        "id": v.id,
        "wersja": v.version_no,
        "akt": unit.act.short_title,
        "przepis": unit.label,
        "przepis_slug": unit.slug,
        "model": v.ai_model,
        "utworzono": v.created_at,
        "tekst_urzedowy": new_unit.text_version.journal_display if new_unit else None,
        "zmiana_przepisu": diff.words(diff.unit_text(old_unit.content), diff.unit_text(new_unit.content))
        if old_unit and new_unit
        else None,
        "poprzednie_objasnienie": {"wersja": previous.version_no, "stan": previous.state}
        if previous
        else None,
        "zmiana_objasnienia": diff.by_sentence(
            diff.sentences(previous.body) if previous else [], new_sentences
        ),
        "odrzucone": report.get("odrzucone", []),
        "uwagi": report.get("uwagi") or None,
    }


class DecisionError(Exception):
    pass


def decide(s: Session, v: ExplanationVersion, *, accept: bool, editor: Editor, comment: str) -> None:
    """Zatwierdzenie publikuje szkic z nazwiskiem recenzenta; odrzucenie zwraca go do szkiców."""
    if v.ai_model is None or v.state != EditorialState.RECENZJA:
        raise DecisionError("Ten szkic AI nie czeka na recenzję.")
    if not editor.can("recenzent"):
        raise DecisionError("O szkicu AI decyduje recenzent.")
    if accept:
        transition(s, v, EditorialState.ZATWIERDZONY, editor, comment)
        transition(s, v, EditorialState.OPUBLIKOWANY, editor, comment)
    else:
        transition(s, v, EditorialState.SZKIC, editor, f"Odrzucony: {comment}")
