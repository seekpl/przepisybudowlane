"""Kontrakt publicznego API (OpenAPI generuje FastAPI z tych modeli)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

FreshnessStatus = Literal["potwierdzona", "zmiana", "przejsciowa", "niepotwierdzona", "zawieszona"]
TextTypeName = Literal["ogloszony", "jednolity", "kompilacja", "nierozpoznany"]
NodeKind = Literal["pytanie", "wynik"]
ExplanationStatus = Literal["brak", "opublikowane", "zawieszone", "cofniete"]


def as_status(value: str) -> FreshnessStatus:
    """Wartości z bazy są zawężane do literałów kontraktu; pydantic sprawdzi je przy serializacji."""
    return cast(FreshnessStatus, value)


def as_text_type(value: str | None) -> TextTypeName | None:
    return cast(TextTypeName | None, value)


class Paragraph(BaseModel):
    unit: str
    text: str


class Notice(BaseModel):
    status: FreshnessStatus
    code: str
    title: str
    body: str


class FreshnessOut(BaseModel):
    status: FreshnessStatus
    date: dt.date | None
    effective_date: dt.date | None
    notices: list[Notice]
    confirmed_at: dt.datetime | None
    confirmation_scope: str | None


class ActRef(BaseModel):
    slug: str
    eli: str
    short_title: str
    abbrev: str
    official_url: str


class UnitRef(BaseModel):
    slug: str
    label: str
    display_label: str
    title: str | None
    url: str


class CitationOut(BaseModel):
    act: str
    journal: str
    unit: str
    as_of: dt.date | None
    eli: str | None
    url: str | None
    text: str = Field(description="Gotowy cytat do skopiowania: akt, publikator, jednostka")


class ExplanationOut(BaseModel):
    version_id: int
    version_no: int
    state: str
    title: str | None
    paragraphs: list[str]
    is_demo: bool
    author: str
    reviewer: str | None
    verified_on: dt.date | None
    published_at: dt.datetime | None
    suspended_reason: str | None
    permalink: str


class AmendmentOut(BaseModel):
    eli: str
    journal: str
    title: str
    published_on: dt.date | None
    entry_into_force: dt.date | None
    later_than_text: bool
    url: str


class ValidityOut(BaseModel):
    kind: str
    valid_from: dt.date | None
    valid_to: dt.date | None
    basis: str | None
    title: str | None
    source: str


class VersionOut(BaseModel):
    unit_version_id: int
    journal: str
    text_type: TextTypeName
    legal_status_date: dt.date | None
    recorded_at: dt.datetime
    is_current: bool
    permalink: str


class ExplanationVersionOut(BaseModel):
    id: int
    version_no: int
    state: str
    published_at: dt.datetime | None
    verified_on: dt.date | None
    permalink: str


class RelatedOut(BaseModel):
    kind: Literal["sciezka", "kreator", "pojecie"]
    title: str
    url: str


class ProvisionSummary(BaseModel):
    slug: str
    title: str | None
    display_label: str
    act: ActRef
    text_type: TextTypeName | None
    freshness: FreshnessOut
    has_explanation: bool
    url: str


class ProvisionOut(BaseModel):
    slug: str
    unit_key: str
    label: str
    display_label: str
    title: str | None
    act: ActRef
    text_type: TextTypeName | None
    text_note: str | None
    paragraphs: list[Paragraph]
    freshness: FreshnessOut
    explanation: ExplanationOut | None
    explanation_status: ExplanationStatus
    citation: CitationOut
    amendments: list[AmendmentOut]
    validity: list[ValidityOut]
    versions: list[VersionOut]
    explanation_versions: list[ExplanationVersionOut]
    illustration: str | None
    related: list[RelatedOut]
    permalink: str
    is_archived_version: bool = False
    current_url: str


class TextVersionOut(BaseModel):
    id: int
    text_type: TextTypeName
    journal: str
    source_eli: str | None
    legal_status_date: dt.date | None
    review_state: str
    parse_quality: float | None
    note: str | None
    origin: str
    recorded_at: dt.datetime


class ActOut(BaseModel):
    slug: str
    eli: str
    short_title: str
    abbrev: str
    title: str
    act_kind: str
    area: str
    in_mvp: bool
    official_url: str
    text_format: str
    owner: str | None
    manifest_verified_on: dt.date | None
    relations: list[dict[str, Any]]
    current_text: TextVersionOut | None
    freshness: FreshnessOut
    amendments: list[AmendmentOut]
    validity: list[ValidityOut]
    last_sync_ok: dt.datetime | None
    units: list[UnitRef]


class GlossaryTermOut(BaseModel):
    slug: str
    term: str
    definition: str
    basis: str | None
    units: list[UnitRef]
    see_also: list[dict[str, str]]
    illustration: str | None
    is_demo: bool
    verified_on: dt.date | None
    state: str
    version_id: int


class DefinitionOut(BaseModel):
    """Definicja ustawowa — dosłowne brzmienie punktu przepisu definicyjnego (arkusz, działanie 3.2)."""

    term: str = Field(description="Pojęcie w mianowniku (do alfabetu i wyszukiwania)")
    term_in_text: str = Field(description="Pojęcie tak, jak stoi w przepisie")
    paragraphs: list[Paragraph]
    unit_slug: str
    display_label: str
    act_slug: str
    act_title: str
    journal: str
    freshness: FreshnessStatus
    url: str


class GuideStepOut(BaseModel):
    title: str
    who: str | None
    body: str
    documents: list[str]
    basis: str | None
    unit: UnitRef | None
    link: str | None
    illustration: str | None


class GuideSummary(BaseModel):
    slug: str
    title: str
    summary: str
    steps_count: int
    url: str


class GuideOut(BaseModel):
    slug: str
    title: str
    summary: str
    caveat: str | None
    steps: list[GuideStepOut]
    units: list[UnitRef]
    is_demo: bool
    verified_on: dt.date | None
    state: str
    version_id: int
    version_no: int


class TreeOption(BaseModel):
    label: str
    next: str


class ToCheckOut(BaseModel):
    """Przepis do sprawdzenia przy przypadku, którego kreator nie obejmuje — dosłownie, bez oceny (4.2)."""

    unit_slug: str
    label: str
    intro: str
    paragraphs: list[Paragraph]
    url: str
    rule: dict[str, Any] | None = Field(
        default=None, description="Reguła zatwierdzona przez recenzenta (4.1)"
    )


class TreeNodeOut(BaseModel):
    key: str
    kind: NodeKind
    step_label: str
    question: str | None
    help: str | None
    options: list[TreeOption]
    result_title: str | None
    result_body: str | None
    outcome: str | None
    basis: str | None
    units: list[UnitRef]
    links: list[dict[str, str]]
    status: FreshnessStatus | None
    status_date: dt.date | None
    status_effective_date: dt.date | None
    suspended: bool
    suspended_reason: str | None
    # Dla wyników „poza zakresem”: przepisy do sprawdzenia według odpowiedzi, która tu prowadzi.
    to_check: dict[str, list[ToCheckOut]] = Field(default_factory=dict)


class TreeOut(BaseModel):
    slug: str
    title: str
    intro: str | None
    scope_note: str | None
    root: str
    nodes: dict[str, TreeNodeOut]
    version_id: int
    version_no: int
    is_demo: bool
    verified_on: dt.date | None
    state: str


class TreeSummary(BaseModel):
    slug: str
    title: str
    intro: str | None
    url: str


class SearchHitOut(BaseModel):
    kind: str
    kind_label: str
    ref: str
    title: str
    subtitle: str | None
    snippet: str
    url: str


class SearchOut(BaseModel):
    query: str
    hits: list[SearchHitOut]
    synonyms_used: list[dict[str, Any]]
    matched_all_words: bool


class SynonymOut(BaseModel):
    term: str
    expansions: list[str]
    note: str | None


class ReportIn(BaseModel):
    target_path: str = Field(max_length=500)
    target_label: str | None = Field(default=None, max_length=300)
    unit_slug: str | None = Field(default=None, max_length=160)
    message: str = Field(min_length=5, max_length=5000)
    contact_email: str | None = Field(default=None, max_length=254)
    consent: bool = False


class ReportOut(BaseModel):
    number: str
    due_on: dt.date
    message: str


class RunOut(BaseModel):
    id: int
    started_at: dt.datetime
    finished_at: dt.datetime | None
    status: str
    trigger: str
    stats: dict[str, Any]
    errors: list[dict[str, Any]]


class ActStatusOut(BaseModel):
    slug: str
    short_title: str
    last_sync_ok: dt.datetime | None
    data_age_hours: float | None
    freshness: FreshnessStatus
    text_type: TextTypeName | None
    journal: str | None


class AlarmOut(BaseModel):
    id: int
    title: str
    raised_at: dt.datetime
    details: dict[str, Any]


class StatusOut(BaseModel):
    generated_at: dt.datetime
    threshold_hours: int
    last_success_at: dt.datetime | None
    alarm: AlarmOut | None
    runs: list[RunOut]
    acts: list[ActStatusOut]
    open_tasks: dict[str, int]
    recent_fetch_errors: list[dict[str, Any]]
    demo_content: bool


class HomeOut(BaseModel):
    featured: list[ProvisionSummary]
    guides: list[GuideSummary]
    trees: list[TreeSummary]
    glossary_count: int
    status: dict[str, Any]
