"""Publiczne API — odczyt bez logowania (RODO: bez danych osobowych poza dobrowolnym e-mailem w zgłoszeniu)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import presenters as p
from app.api import schemas as o
from app.config import Settings, get_settings
from app.db import get_session
from app.models import DecisionTree, Guide, LegalAct, LegalUnit, SearchSynonym
from app.modules.content.definitions import statutory_definitions
from app.modules.editorial.workflow import public_version
from app.modules.freshness import service as fresh
from app.modules.ops.status import status as ops_status
from app.modules.reports.service import ReportError, create_report
from app.modules.search.misses import record_miss
from app.modules.search.service import search as run_search

router = APIRouter(prefix="/api/v1", tags=["publiczne"])


def _unit(s: Session, slug: str) -> LegalUnit:
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == slug))
    if unit is None:
        raise HTTPException(404, "Nie znaleźliśmy takiego przepisu.")
    return unit


@router.get("/start", response_model=o.HomeOut, summary="Dane strony startowej")
def home(s: Session = Depends(get_session), settings: Settings = Depends(get_settings)) -> o.HomeOut:
    featured = s.scalars(select(LegalUnit).where(LegalUnit.featured.is_(True)).order_by(LegalUnit.id)).all()
    guides = []
    for g in s.scalars(select(Guide).order_by(Guide.id)):
        gv = public_version(g.versions)
        if gv and gv.state == "opublikowany":
            guides.append(
                o.GuideSummary(
                    slug=g.slug,
                    title=gv.title,
                    summary=gv.summary,
                    steps_count=len(gv.steps),
                    url=f"/sciezki/{g.slug}",
                )
            )
    trees = []
    for t in s.scalars(select(DecisionTree).order_by(DecisionTree.id)):
        tv = public_version(t.versions)
        if tv and tv.state == "opublikowany":
            trees.append(o.TreeSummary(slug=t.slug, title=tv.title, intro=tv.intro, url=f"/kreator/{t.slug}"))
    st = ops_status(s, settings)
    return o.HomeOut(
        featured=[p.provision_summary(s, u) for u in featured],
        guides=guides,
        trees=trees,
        glossary_count=len(p.glossary_out(s)),
        status={
            "last_success_at": st.last_success_at,
            "demo_content": st.demo_content,
            "threshold_hours": st.threshold_hours,
        },
    )


@router.get(
    "/przepisy", response_model=list[o.ProvisionSummary], summary="Karty przepisów wyróżnione przez redakcję"
)
def provisions(s: Session = Depends(get_session)) -> list[o.ProvisionSummary]:
    units = s.scalars(select(LegalUnit).where(LegalUnit.featured.is_(True)).order_by(LegalUnit.id)).all()
    return [p.provision_summary(s, u) for u in units]


@router.get(
    "/przepisy/{slug}",
    response_model=o.ProvisionOut,
    summary="Karta przepisu: tekst, typ, metryka, aktualność, objaśnienie",
)
def provision(
    slug: str,
    objasnienie: int | None = Query(default=None, description="Konkretna wersja objaśnienia (trwały adres)"),
    s: Session = Depends(get_session),
) -> o.ProvisionOut:
    out = p.provision(s, _unit(s, slug), explanation_version_id=objasnienie)
    assert out is not None
    return out


@router.get(
    "/przepisy/{slug}/wersje/{unit_version_id}",
    response_model=o.ProvisionOut,
    summary="Trwały adres konkretnej wersji przepisu",
)
def provision_version(
    slug: str, unit_version_id: int, objasnienie: int | None = None, s: Session = Depends(get_session)
) -> o.ProvisionOut:
    out = p.provision(s, _unit(s, slug), unit_version_id=unit_version_id, explanation_version_id=objasnienie)
    if out is None:
        raise HTTPException(404, "Nie ma takiej wersji tego przepisu.")
    return out


@router.get("/akty", response_model=list[o.ActOut], summary="Manifest aktów z aktualnością i nowelizacjami")
def acts(s: Session = Depends(get_session)) -> list[o.ActOut]:
    return [p.act_out(s, a) for a in s.scalars(select(LegalAct).order_by(LegalAct.id))]


@router.get("/akty/{slug}", response_model=o.ActOut)
def act(slug: str, s: Session = Depends(get_session)) -> o.ActOut:
    a = s.scalar(select(LegalAct).where(LegalAct.slug == slug))
    if a is None:
        raise HTTPException(404, "Nie znaleźliśmy takiego aktu.")
    return p.act_out(s, a)


@router.get(
    "/szukaj",
    response_model=o.SearchOut,
    summary="Wyszukiwarka z polską odmianą i jawnym słownikiem synonimów",
)
def search(q: str = Query(min_length=1, max_length=200), s: Session = Depends(get_session)) -> o.SearchOut:
    r = run_search(s, q)
    if not r.hits:
        record_miss(s, q)  # tylko znormalizowane zapytanie i licznik — źródło propozycji synonimów
        s.commit()
    return o.SearchOut(
        query=r.query,
        synonyms_used=r.synonyms_used,
        matched_all_words=r.matched_all_words,
        hits=[
            o.SearchHitOut(
                kind=h.kind,
                kind_label=h.kind_label,
                ref=h.ref,
                title=h.title,
                subtitle=h.subtitle,
                snippet=h.snippet,
                url=h.url,
            )
            for h in r.hits
        ],
    )


@router.get("/synonimy", response_model=list[o.SynonymOut], summary="Jawny słownik synonimów wyszukiwarki")
def synonyms(s: Session = Depends(get_session)) -> list[o.SynonymOut]:
    return [
        o.SynonymOut(term=x.term, expansions=x.expansions, note=x.note)
        for x in s.scalars(select(SearchSynonym).order_by(SearchSynonym.term))
    ]


@router.get("/slowniczek", response_model=list[o.GlossaryTermOut])
def glossary(s: Session = Depends(get_session)) -> list[o.GlossaryTermOut]:
    return p.glossary_out(s)


@router.get(
    "/definicje",
    response_model=list[o.DefinitionOut],
    summary="Definicje ustawowe z przyjętych tekstów aktów — cytat, nie interpretacja",
)
def definitions(s: Session = Depends(get_session)) -> list[o.DefinitionOut]:
    acts = {a.slug: a for a in s.scalars(select(LegalAct))}
    status = {slug: o.as_status(fresh.for_act(s, a).status) for slug, a in acts.items()}
    return [
        o.DefinitionOut(
            term=d.term,
            term_in_text=d.term_in_text,
            paragraphs=[o.Paragraph(**x) for x in d.paragraphs],
            unit_slug=d.unit_slug,
            display_label=f"{acts[d.act_slug].abbrev} {d.unit_label}",
            act_slug=d.act_slug,
            act_title=d.act_title,
            journal=d.journal,
            freshness=status[d.act_slug],
            url=f"/przepis/{d.unit_slug}",
        )
        for d in statutory_definitions(s)
    ]


@router.get("/sciezki", response_model=list[o.GuideSummary])
def guides(s: Session = Depends(get_session)) -> list[o.GuideSummary]:
    out = []
    for g in s.scalars(select(Guide).order_by(Guide.id)):
        gv = public_version(g.versions)
        if gv and gv.state == "opublikowany":
            out.append(
                o.GuideSummary(
                    slug=g.slug,
                    title=gv.title,
                    summary=gv.summary,
                    steps_count=len(gv.steps),
                    url=f"/sciezki/{g.slug}",
                )
            )
    return out


@router.get("/sciezki/{slug}", response_model=o.GuideOut)
def guide(slug: str, s: Session = Depends(get_session)) -> o.GuideOut:
    g = s.scalar(select(Guide).where(Guide.slug == slug))
    out = p.guide_out(s, g) if g else None
    if out is None:
        raise HTTPException(404, "Nie znaleźliśmy takiej ścieżki.")
    return out


@router.get(
    "/kreatory/{slug}",
    response_model=o.TreeOut,
    summary="Opublikowana wersja drzewka decyzyjnego ze statusami wyników",
)
def tree(slug: str, s: Session = Depends(get_session)) -> o.TreeOut:
    t = s.scalar(select(DecisionTree).where(DecisionTree.slug == slug))
    out = p.tree_out(s, t) if t else None
    if out is None:
        raise HTTPException(404, "Nie znaleźliśmy takiego kreatora.")
    return out


@router.post("/zgloszenia", response_model=o.ReportOut, status_code=201, summary="Zgłoś błąd w treści")
def report(
    body: o.ReportIn, s: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> o.ReportOut:
    try:
        r = create_report(
            s,
            settings,
            target_path=body.target_path,
            target_label=body.target_label,
            unit_slug=body.unit_slug,
            message=body.message,
            contact_email=body.contact_email,
            consent=body.consent,
        )
    except ReportError as exc:
        raise HTTPException(422, str(exc)) from exc
    s.commit()
    return o.ReportOut(
        number=f"ZB-{r.id}",
        due_on=r.due_on,
        message=f"Dziękujemy. Zgłoszenie ma numer ZB-{r.id}. Sprawdzimy je do {r.due_on.day}.{r.due_on.month:02d}.{r.due_on.year}.",
    )


@router.get(
    "/stan", response_model=o.StatusOut, summary="Stan danych: synchronizacja, wiek danych, zaległe zadania"
)
def data_status(s: Session = Depends(get_session), settings: Settings = Depends(get_settings)) -> o.StatusOut:
    return ops_status(s, settings)
