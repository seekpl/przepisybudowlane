"""Stany redakcyjne: szkic → recenzja → zatwierdzony → opublikowany; zawieszony lub cofnięty.

Zasady z planu:
- autor nie zatwierdza własnej treści (recenzent musi być inną osobą),
- publikujemy tylko wersję zatwierdzoną, z datą weryfikacji,
- każde przejście trafia do ``editorial_event`` z autorem i datą,
- po wykryciu zmiany źródła system sam zawiesza opublikowaną treść.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now, today
from app.config import Editor
from app.history import record
from app.models import (
    DecisionTreeVersion,
    EditorialEvent,
    EditorialState,
    Explanation,
    ExplanationVersion,
    GlossaryTermVersion,
    GuideVersion,
    LegalTextVersion,
    LegalUnitVersion,
    TextReview,
)

S = EditorialState

ENTITY_MODELS: dict[str, Any] = {
    "explanation_version": ExplanationVersion,
    "decision_tree_version": DecisionTreeVersion,
    "guide_version": GuideVersion,
    "glossary_term_version": GlossaryTermVersion,
}

EditorialVersion = ExplanationVersion | DecisionTreeVersion | GuideVersion | GlossaryTermVersion

# Stany, w których wersja kiedykolwiek była publiczna — najnowsza z nich decyduje o tym, co widzi użytkownik.
EVER_PUBLISHED = (S.OPUBLIKOWANY, S.ZAWIESZONY, S.COFNIETY)


class WorkflowError(Exception):
    pass


def entity_name(version: object) -> str:
    for name, model in ENTITY_MODELS.items():
        if isinstance(version, model):
            return name
    raise WorkflowError(f"Nieobsługiwany typ treści: {type(version).__name__}")


def _event(
    s: Session,
    version: EditorialVersion,
    from_state: str | None,
    to_state: str,
    actor: str,
    comment: str | None,
) -> None:
    entity = entity_name(version)
    s.add(
        EditorialEvent(
            entity=entity,
            entity_id=version.id,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            comment=comment,
        )
    )
    record(
        s,
        actor=actor,
        entity=entity,
        entity_id=version.id,
        action=f"{from_state or '-'}→{to_state}",
        komentarz=comment,
    )


def _check_explanation_is_current(s: Session, version: ExplanationVersion) -> None:
    """Objaśnienie można opublikować tylko do brzmienia, które jest dziś pokazywane."""
    explanation = s.get(Explanation, version.explanation_id)
    assert explanation is not None
    current = s.scalar(
        select(LegalUnitVersion)
        .join(LegalTextVersion, LegalTextVersion.id == LegalUnitVersion.text_version_id)
        .where(
            LegalUnitVersion.unit_id == explanation.unit_id,
            LegalTextVersion.review_state == TextReview.ZAAKCEPTOWANY,
        )
        .order_by(LegalTextVersion.recorded_at.desc(), LegalTextVersion.id.desc())
    )
    if current is None:
        raise WorkflowError(
            "Nie ma zaakceptowanego tekstu tej jednostki — objaśnienia nie można opublikować."
        )
    if version.based_on_unit_version_id != current.id:
        raise WorkflowError(
            "Objaśnienie opisuje inne brzmienie przepisu niż obecnie pokazywane. Zaktualizuj je."
        )


def transition(
    s: Session, version: EditorialVersion, to_state: str, editor: Editor, comment: str | None = None
) -> None:
    current = version.state
    name = editor.name
    if (current, to_state) == (S.SZKIC, S.RECENZJA):
        if name != version.author:
            raise WorkflowError("Do recenzji przekazuje autor szkicu.")
    elif (current, to_state) == (S.RECENZJA, S.SZKIC):
        if name != version.author and not editor.can("recenzent"):
            raise WorkflowError("Szkic do poprawy zwraca recenzent albo autor.")
    elif (current, to_state) == (S.RECENZJA, S.ZATWIERDZONY):
        if not editor.can("recenzent"):
            raise WorkflowError("Zatwierdza tylko osoba z rolą recenzenta.")
        if name == version.author:
            raise WorkflowError("Autor nie zatwierdza własnej treści — potrzebny niezależny recenzent.")
        version.reviewer = name
        version.verified_on = today()
    elif (current, to_state) == (S.ZATWIERDZONY, S.OPUBLIKOWANY):
        if not (editor.can("redaktor") or editor.can("recenzent")):
            raise WorkflowError("Publikuje redakcja.")
        if version.reviewer is None or version.verified_on is None:
            raise WorkflowError("Brak zatwierdzenia recenzenta lub daty weryfikacji.")
        if isinstance(version, ExplanationVersion):
            _check_explanation_is_current(s, version)
        version.published_at = now()
    elif (current, to_state) == (S.OPUBLIKOWANY, S.ZAWIESZONY):
        if not comment:
            raise WorkflowError("Podaj powód zawieszenia — zobaczy go redakcja.")
    elif (current, to_state) in ((S.OPUBLIKOWANY, S.COFNIETY), (S.ZAWIESZONY, S.COFNIETY)):
        if not comment:
            raise WorkflowError("Podaj powód cofnięcia.")
    elif (current, to_state) == (S.ZAWIESZONY, S.OPUBLIKOWANY):
        # Ponowne potwierdzenie po zmianie źródła: jak zatwierdzenie — przez recenzenta, nie przez autora.
        if not editor.can("recenzent") or name == version.author:
            raise WorkflowError("Zawieszoną treść przywraca niezależny recenzent po ponownym sprawdzeniu.")
        if isinstance(version, ExplanationVersion):
            _check_explanation_is_current(s, version)
        version.reviewer = name
        version.verified_on = today()
        version.published_at = now()
    else:
        raise WorkflowError(f"Niedozwolone przejście: {current} → {to_state}.")
    version.state = to_state
    _event(s, version, current, to_state, name, comment)


def system_suspend(s: Session, version: EditorialVersion, *, reason: str, actor: str) -> None:
    if version.state != S.OPUBLIKOWANY:
        return
    version.state = S.ZAWIESZONY
    _event(s, version, S.OPUBLIKOWANY, S.ZAWIESZONY, actor, reason)


def public_version[V: EditorialVersion](versions: Sequence[V]) -> V | None:
    """Najnowsza wersja, która kiedykolwiek była publiczna. Starsze zostają w historii pod trwałym adresem."""
    candidates = [v for v in versions if v.state in EVER_PUBLISHED]
    if not candidates:
        return None
    return max(candidates, key=lambda v: (v.version_no, v.id))


def suspension_reason(s: Session, version: EditorialVersion) -> str | None:
    if version.state not in (S.ZAWIESZONY, S.COFNIETY):
        return None
    event = s.scalar(
        select(EditorialEvent)
        .where(
            EditorialEvent.entity == entity_name(version),
            EditorialEvent.entity_id == version.id,
            EditorialEvent.to_state == version.state,
        )
        .order_by(EditorialEvent.id.desc())
    )
    return event.comment if event else None
