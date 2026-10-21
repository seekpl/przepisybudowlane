"""Model danych.

Dwie osie czasu (plan, „Źródła danych, model czasu i aktualność”):
- czas obowiązywania prawa: ``legal_validity_interval``, ``detected_amendment``, daty w ``legal_text_version``;
- czas systemowy: ``recorded_at`` / ``created_at`` przy każdym wierszu, ``source_fetch`` i ``system_history``.

Historii nie nadpisujemy: wersje tekstów, jednostek, objaśnień i drzewek tylko dopisujemy.
Korekta przedziału obowiązywania to nowy wiersz z ``supersedes_id``.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import now
from app.db import Base

Json = JSON().with_variant(JSONB(), "postgresql")


class TextType(StrEnum):
    OGLOSZONY = "ogloszony"
    JEDNOLITY = "jednolity"
    KOMPILACJA = "kompilacja"
    NIEROZPOZNANY = "nierozpoznany"


class TextReview(StrEnum):
    ZAAKCEPTOWANY = "zaakceptowany"
    DO_KONTROLI = "do_kontroli"
    ODRZUCONY = "odrzucony"


class ValidityKind(StrEnum):
    OBOWIAZUJE = "obowiazuje"
    UTRACIL_MOC = "utracil_moc"
    STOSOWANY_PRZEJSCIOWO = "stosowany_przejsciowo"
    ZAWIESZONY = "zawieszony"


class EditorialState(StrEnum):
    SZKIC = "szkic"
    RECENZJA = "recenzja"
    ZATWIERDZONY = "zatwierdzony"
    OPUBLIKOWANY = "opublikowany"
    ZAWIESZONY = "zawieszony"
    COFNIETY = "cofniety"


class TaskKind(StrEnum):
    NOWELIZACJA = "nowelizacja"
    ZMIANA_TEKSTU = "zmiana_tekstu"
    KONTROLA_PARSERA = "kontrola_parsera"
    AWARIA_SYNCHRONIZACJI = "awaria_synchronizacji"
    ZGLOSZENIE_BLEDU = "zgloszenie_bledu"


class SyncStatus(StrEnum):
    W_TOKU = "w_toku"
    SUKCES = "sukces"
    CZESCIOWY = "czesciowy"
    BLAD = "blad"
    # Alarm kontraktu źródła: przebieg nie pobiera niczego, dopóki człowiek nie zamknie alarmu.
    WSTRZYMANY = "wstrzymany"


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=now, nullable=False)


# --- Rejestr aktów i źródeł ---------------------------------------------------------------


class LegalAct(Base):
    """Pozycja manifestu aktów: zatwierdzona lista, nie lista portali."""

    __tablename__ = "legal_act"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    eli: Mapped[str] = mapped_column(String(40), unique=True)
    short_title: Mapped[str] = mapped_column(String(200))
    abbrev: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    citation_name: Mapped[str] = mapped_column(Text)
    act_kind: Mapped[str] = mapped_column(String(40))
    area: Mapped[str] = mapped_column(String(80))
    in_mvp: Mapped[bool] = mapped_column(Boolean, default=True)
    official_url: Mapped[str] = mapped_column(Text)
    text_format: Mapped[str] = mapped_column(String(20), default="nieznany")
    owner: Mapped[str | None] = mapped_column(String(120))
    manifest_verified_on: Mapped[date | None] = mapped_column(Date)
    relations: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    created_at: Mapped[datetime] = _ts()

    units: Mapped[list[LegalUnit]] = relationship(back_populates="act")


class SourceSnapshot(Base):
    """Surowa odpowiedź źródła. Treść leży w archiwum pod kluczem SHA-256, tu metryka."""

    __tablename__ = "source_snapshot"
    __table_args__ = (
        UniqueConstraint("url", "sha256", name="uq_snapshot_url_sha"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_snapshot_sha256"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int | None] = mapped_column(ForeignKey("legal_act.id"))
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120))
    http_status: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(Text)
    parser_version: Mapped[str | None] = mapped_column(String(40))
    first_fetched_at: Mapped[datetime] = _ts()


class SourceFetch(Base):
    """Każda próba pobrania — także nieudana. Z niej liczymy wiek danych."""

    __tablename__ = "source_fetch"
    __table_args__ = (Index("ix_fetch_act_ok", "act_id", "ok", "fetched_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int | None] = mapped_column(ForeignKey("sync_run.id"))
    act_id: Mapped[int | None] = mapped_column(ForeignKey("legal_act.id"))
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30))
    fetched_at: Mapped[datetime] = _ts()
    http_status: Mapped[int | None] = mapped_column(Integer)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("source_snapshot.id"))
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class SourceVerification(Base):
    """Ręczne potwierdzenie przez człowieka (np. porównanie z Dz.U.) — też punkt odniesienia dla aktualności."""

    __tablename__ = "source_verification"

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("legal_act.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("legal_unit.id"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str] = mapped_column(String(120))
    method: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = _ts()


# --- Wersje aktów i jednostek redakcyjnych ------------------------------------------------


class LegalTextVersion(Base):
    """Wersja tekstu aktu. Niezmiennik (arkusz, działanie 2.1): każda pochodzi z migawki ELI z sumą SHA-256 —
    tekstu prawa nie da się wpisać ręcznie, ani w danych startowych, ani w panelu."""

    __tablename__ = "legal_text_version"
    __table_args__ = (
        UniqueConstraint("act_id", "snapshot_id", name="uq_text_version_snapshot"),
        CheckConstraint("origin = 'eli'", name="ck_text_version_from_eli"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("legal_act.id"))
    text_type: Mapped[str] = mapped_column(String(20))
    source_eli: Mapped[str | None] = mapped_column(String(40))
    journal_display: Mapped[str] = mapped_column(String(200))
    legal_status_date: Mapped[date | None] = mapped_column(Date)
    published_on: Mapped[date | None] = mapped_column(Date)
    # ELI nowelizacji naniesionych w tym tekście (dla kompilacji i tekstów jednolitych).
    incorporated: Mapped[list[str]] = mapped_column(Json, default=list)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("source_snapshot.id"))
    origin: Mapped[str] = mapped_column(String(20), default="eli")
    parser_version: Mapped[str | None] = mapped_column(String(40))
    parse_quality: Mapped[float | None] = mapped_column(Float)
    review_state: Mapped[str] = mapped_column(String(20))
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = _ts()

    act: Mapped[LegalAct] = relationship()


class LegalUnit(Base):
    """Trwała tożsamość jednostki redakcyjnej (art., §, ust., pkt) niezależna od wersji tekstu."""

    __tablename__ = "legal_unit"
    __table_args__ = (UniqueConstraint("act_id", "unit_key", name="uq_unit_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("legal_act.id"))
    unit_key: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str | None] = mapped_column(String(200))
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    illustration: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = _ts()

    act: Mapped[LegalAct] = relationship(back_populates="units")


class LegalUnitVersion(Base):
    __tablename__ = "legal_unit_version"
    __table_args__ = (UniqueConstraint("unit_id", "text_version_id", name="uq_unit_in_text"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("legal_unit.id"))
    text_version_id: Mapped[int] = mapped_column(ForeignKey("legal_text_version.id"))
    # Lista akapitów {"unit": "§ 12. 1.", "text": "..."} — tekst bez zmian redakcyjnych.
    content: Mapped[list[dict[str, str]]] = mapped_column(Json)
    content_hash: Mapped[str] = mapped_column(String(64))
    recorded_at: Mapped[datetime] = _ts()

    unit: Mapped[LegalUnit] = relationship()
    text_version: Mapped[LegalTextVersion] = relationship()


class LegalValidityInterval(Base):
    """Kiedy akt lub jednostka obowiązuje. Korekta = nowy wiersz z ``supersedes_id``."""

    __tablename__ = "legal_validity_interval"

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("legal_act.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("legal_unit.id"))
    kind: Mapped[str] = mapped_column(String(30))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    basis: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("legal_validity_interval.id"))
    recorded_at: Mapped[datetime] = _ts()
    recorded_by: Mapped[str] = mapped_column(String(120))


class DetectedAmendment(Base):
    """Nowelizacja opublikowana po deklarowanym stanie prawnym tekstu — wykryta automatycznie."""

    __tablename__ = "detected_amendment"
    __table_args__ = (UniqueConstraint("act_id", "amending_eli", name="uq_amendment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("legal_act.id"))
    amending_eli: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    journal_display: Mapped[str] = mapped_column(String(200))
    published_on: Mapped[date | None] = mapped_column(Date)
    entry_into_force: Mapped[date | None] = mapped_column(Date)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("source_snapshot.id"))
    detected_at: Mapped[datetime] = _ts()


class SystemHistory(Base):
    """Dziennik dopisywany: co, kiedy i kto zmienił w systemie."""

    __tablename__ = "system_history"
    __table_args__ = (Index("ix_history_entity", "entity", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recorded_at: Mapped[datetime] = _ts()
    actor: Mapped[str] = mapped_column(String(120))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(60))
    data: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


# --- Redakcja i publikacja ----------------------------------------------------------------


class EditorialVersionMixin:
    state: Mapped[str] = mapped_column(String(20), default=EditorialState.SZKIC)
    author: Mapped[str] = mapped_column(String(120))
    reviewer: Mapped[str | None] = mapped_column(String(120))
    verified_on: Mapped[date | None] = mapped_column(Date)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _ts()
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Explanation(Base):
    __tablename__ = "explanation"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("legal_unit.id"), unique=True)
    created_at: Mapped[datetime] = _ts()

    unit: Mapped[LegalUnit] = relationship()
    versions: Mapped[list[ExplanationVersion]] = relationship(back_populates="explanation")


class ExplanationVersion(EditorialVersionMixin, Base):
    __tablename__ = "explanation_version"
    __table_args__ = (UniqueConstraint("explanation_id", "version_no", name="uq_explanation_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    explanation_id: Mapped[int] = mapped_column(ForeignKey("explanation.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    based_on_unit_version_id: Mapped[int | None] = mapped_column(ForeignKey("legal_unit_version.id"))

    explanation: Mapped[Explanation] = relationship(back_populates="versions")


class DecisionTree(Base):
    __tablename__ = "decision_tree"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = _ts()

    versions: Mapped[list[DecisionTreeVersion]] = relationship(back_populates="tree")


class DecisionTreeVersion(EditorialVersionMixin, Base):
    __tablename__ = "decision_tree_version"
    __table_args__ = (UniqueConstraint("tree_id", "version_no", name="uq_tree_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tree_id: Mapped[int] = mapped_column(ForeignKey("decision_tree.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    intro: Mapped[str | None] = mapped_column(Text)
    scope_note: Mapped[str | None] = mapped_column(Text)
    root_node_key: Mapped[str] = mapped_column(String(60))

    tree: Mapped[DecisionTree] = relationship(back_populates="versions")
    nodes: Mapped[list[DecisionTreeNodeVersion]] = relationship(back_populates="tree_version")


class DecisionTreeNodeVersion(Base):
    """Węzeł drzewka w danej wersji. Powiązany z jednostkami redakcyjnymi — po ich zmianie zawieszany."""

    __tablename__ = "decision_tree_node_version"
    __table_args__ = (UniqueConstraint("tree_version_id", "node_key", name="uq_tree_node"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tree_version_id: Mapped[int] = mapped_column(ForeignKey("decision_tree_version.id"))
    node_key: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))  # pytanie | wynik
    step_label: Mapped[str] = mapped_column(String(80))
    question: Mapped[str | None] = mapped_column(Text)
    help: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list[dict[str, str]]] = mapped_column(Json, default=list)
    result_title: Mapped[str | None] = mapped_column(Text)
    result_body: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(30))
    basis_label: Mapped[str | None] = mapped_column(Text)
    unit_slugs: Mapped[list[str]] = mapped_column(Json, default=list)
    links: Mapped[list[dict[str, str]]] = mapped_column(Json, default=list)

    tree_version: Mapped[DecisionTreeVersion] = relationship(back_populates="nodes")


class Guide(Base):
    """Ścieżka krok po kroku."""

    __tablename__ = "guide"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = _ts()

    versions: Mapped[list[GuideVersion]] = relationship(back_populates="guide")


class GuideVersion(EditorialVersionMixin, Base):
    __tablename__ = "guide_version"
    __table_args__ = (UniqueConstraint("guide_id", "version_no", name="uq_guide_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    guide_id: Mapped[int] = mapped_column(ForeignKey("guide.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    caveat: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(Json)
    unit_slugs: Mapped[list[str]] = mapped_column(Json, default=list)

    guide: Mapped[Guide] = relationship(back_populates="versions")


class GlossaryTerm(Base):
    __tablename__ = "glossary_term"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = _ts()

    versions: Mapped[list[GlossaryTermVersion]] = relationship(back_populates="term")


class GlossaryTermVersion(EditorialVersionMixin, Base):
    __tablename__ = "glossary_term_version"
    __table_args__ = (UniqueConstraint("term_id", "version_no", name="uq_term_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("glossary_term.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    term_label: Mapped[str] = mapped_column(String(120))
    definition: Mapped[str] = mapped_column(Text)
    basis_label: Mapped[str | None] = mapped_column(Text)
    unit_slugs: Mapped[list[str]] = mapped_column(Json, default=list)
    see_also: Mapped[list[str]] = mapped_column(Json, default=list)
    illustration: Mapped[str | None] = mapped_column(String(80))

    term: Mapped[GlossaryTerm] = relationship(back_populates="versions")


class ContentFlag(Base):
    """Zawieszenie fragmentu treści (np. węzła kreatora) do przeglądu po zmianie źródła."""

    __tablename__ = "content_flag"
    __table_args__ = (Index("ix_flag_entity", "entity", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()
    created_by: Mapped[str] = mapped_column(String(120))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(120))


class EditorialEvent(Base):
    """Każde przejście stanu redakcyjnego — z autorem i datą."""

    __tablename__ = "editorial_event"
    __table_args__ = (Index("ix_editorial_event_entity", "entity", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int] = mapped_column(Integer)
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()


class EditorialTask(Base):
    __tablename__ = "editorial_task"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    act_id: Mapped[int | None] = mapped_column(ForeignKey("legal_act.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("legal_unit.id"))
    state: Mapped[str] = mapped_column(String(20), default="otwarte")
    # Idempotencja: to samo zdarzenie nie tworzy drugiego zadania.
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = _ts()
    due_on: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(120))
    resolution: Mapped[str | None] = mapped_column(Text)


class ErrorReport(Base):
    __tablename__ = "error_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_path: Mapped[str] = mapped_column(Text)
    target_label: Mapped[str | None] = mapped_column(Text)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("legal_unit.id"))
    message: Mapped[str] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _ts()
    due_on: Mapped[date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(20), default="nowe")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("editorial_task.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_purge_after: Mapped[date | None] = mapped_column(Date)


# --- Synchronizacja i operacje ------------------------------------------------------------


class SyncRun(Base):
    __tablename__ = "sync_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = _ts()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=SyncStatus.W_TOKU)
    trigger: Mapped[str] = mapped_column(String(40))
    since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoint"

    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_success_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int] = mapped_column(ForeignKey("sync_run.id"))


class SourceAlarm(Base):
    """Alarm źródła (np. zmiana schematu ELI). Otwarty alarm wstrzymuje synchronizację tego źródła."""

    __tablename__ = "source_alarm"
    __table_args__ = (Index("ix_alarm_open", "source", "resolved_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("sync_run.id"))
    raised_at: Mapped[datetime] = _ts()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(120))
    resolution: Mapped[str | None] = mapped_column(Text)


# --- Wyszukiwanie -------------------------------------------------------------------------


class SearchDocument(Base):
    """Indeks pochodny — przebudowywany z treści opublikowanych, nie jest historią."""

    __tablename__ = "search_document"
    __table_args__ = (
        UniqueConstraint("kind", "ref", name="uq_search_doc"),
        Index("ix_search_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    ref: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    tsv: Mapped[Any] = mapped_column(TSVECTOR)
    updated_at: Mapped[datetime] = _ts()


class SearchSynonym(Base):
    """Jawny słownik potocznych synonimów („płot” → ogrodzenie)."""

    __tablename__ = "search_synonym"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(80), unique=True)
    expansions: Mapped[list[str]] = mapped_column(Json)
    note: Mapped[str | None] = mapped_column(Text)
