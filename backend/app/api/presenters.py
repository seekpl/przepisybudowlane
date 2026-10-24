"""Budowanie odpowiedzi API z modeli — jedno miejsce, w którym karta przepisu składa się w całość."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as o
from app.models import (
    DecisionTree,
    EditorialState,
    Explanation,
    ExplanationVersion,
    GlossaryTerm,
    Guide,
    LegalAct,
    LegalTextVersion,
    LegalUnit,
    LegalUnitVersion,
    TextReview,
)
from app.modules.content.to_check import to_check
from app.modules.editorial.flags import active_flags
from app.modules.editorial.workflow import public_version, suspension_reason
from app.modules.freshness import service as fresh
from app.modules.freshness.engine import SEVERITY, Amendment, Freshness, Reason, is_later_than
from app.texts import words_date

S = EditorialState


def freshness_out(f: Freshness) -> o.FreshnessOut:
    return o.FreshnessOut(
        status=o.as_status(f.status),
        date=f.date,
        effective_date=f.effective_date,
        notices=[
            o.Notice(status=o.as_status(r.status), code=r.code, title=r.title, body=r.body) for r in f.notices
        ],
        confirmed_at=f.confirmed_at,
        confirmation_scope=f.confirmation_scope,
    )


def act_ref(act: LegalAct) -> o.ActRef:
    return o.ActRef(
        slug=act.slug,
        eli=act.eli,
        short_title=act.short_title,
        abbrev=act.abbrev,
        official_url=act.official_url,
    )


def unit_ref(unit: LegalUnit, act: LegalAct) -> o.UnitRef:
    return o.UnitRef(
        slug=unit.slug,
        label=unit.label,
        display_label=f"{act.abbrev} {unit.label}",
        title=unit.title,
        url=f"/przepis/{unit.slug}",
    )


def unit_refs(s: Session, slugs: list[str]) -> list[o.UnitRef]:
    if not slugs:
        return []
    units = {u.slug: u for u in s.scalars(select(LegalUnit).where(LegalUnit.slug.in_(slugs)))}
    out = []
    for slug in slugs:
        u = units.get(slug)
        if u is not None:
            act = s.get(LegalAct, u.act_id)
            assert act is not None
            out.append(unit_ref(u, act))
    return out


def eli_url(eli: str | None) -> str | None:
    return f"https://eli.gov.pl/eli/{eli}" if eli else None


def amendments_out(s: Session, act: LegalAct, text: LegalTextVersion | None) -> list[o.AmendmentOut]:
    out = []
    for a in fresh.amendments(s, act.id):
        later = bool(
            text is not None
            and text.legal_status_date is not None
            and a.amending_eli not in (text.incorporated or [])
            and is_later_than(
                Amendment(a.amending_eli, a.journal_display, a.published_on, a.entry_into_force),
                text.legal_status_date,
            )
        )
        out.append(
            o.AmendmentOut(
                eli=a.amending_eli,
                journal=a.journal_display,
                title=a.title,
                published_on=a.published_on,
                entry_into_force=a.entry_into_force,
                later_than_text=later,
                url=eli_url(a.amending_eli) or "",
            )
        )
    return out


def validity_out(s: Session, act_id: int, unit_id: int | None) -> list[o.ValidityOut]:
    return [
        o.ValidityOut(
            kind=iv.kind,
            valid_from=iv.valid_from,
            valid_to=iv.valid_to,
            basis=iv.basis,
            title=iv.title,
            source=iv.source,
        )
        for iv in fresh.active_intervals(s, act_id, unit_id)
    ]


def _explanation_out(s: Session, unit: LegalUnit, version: ExplanationVersion) -> o.ExplanationOut:
    return o.ExplanationOut(
        version_id=version.id,
        version_no=version.version_no,
        state=version.state,
        title=version.title,
        paragraphs=[p.strip() for p in version.body.split("\n\n") if p.strip()],
        is_demo=version.is_demo,
        ai_assisted=version.ai_model is not None,
        author=version.author,
        reviewer=version.reviewer,
        verified_on=version.verified_on,
        published_at=version.published_at,
        suspended_reason=suspension_reason(s, version),
        permalink=f"/przepis/{unit.slug}?objasnienie={version.id}",
    )


def related_for_unit(s: Session, unit: LegalUnit) -> list[o.RelatedOut]:
    related: list[o.RelatedOut] = []
    for guide in s.scalars(select(Guide).order_by(Guide.id)):
        gv = public_version(guide.versions)
        if (
            gv
            and gv.state == S.OPUBLIKOWANY
            and (unit.slug in (gv.unit_slugs or []) or any(st.get("unit") == unit.slug for st in gv.steps))
        ):
            related.append(o.RelatedOut(kind="sciezka", title=gv.title, url=f"/sciezki/{guide.slug}"))
    for tree in s.scalars(select(DecisionTree).order_by(DecisionTree.id)):
        tv = public_version(tree.versions)
        if tv and tv.state == S.OPUBLIKOWANY and any(unit.slug in (n.unit_slugs or []) for n in tv.nodes):
            related.append(o.RelatedOut(kind="kreator", title=tv.title, url=f"/kreator/{tree.slug}"))
    for term in s.scalars(select(GlossaryTerm).order_by(GlossaryTerm.id)):
        termv = public_version(term.versions)
        if termv and termv.state == S.OPUBLIKOWANY and unit.slug in (termv.unit_slugs or []):
            related.append(
                o.RelatedOut(kind="pojecie", title=termv.term_label, url=f"/slowniczek#{term.slug}")
            )
    return related


def provision(
    s: Session,
    unit: LegalUnit,
    *,
    unit_version_id: int | None = None,
    explanation_version_id: int | None = None,
) -> o.ProvisionOut | None:
    act = s.get(LegalAct, unit.act_id)
    assert act is not None
    current = fresh.unit_text(s, unit)
    shown_uv, shown_tv = current.unit_version, current.text_version
    archived = False
    if unit_version_id is not None:
        pair = s.execute(
            select(LegalUnitVersion, LegalTextVersion)
            .join(LegalTextVersion, LegalTextVersion.id == LegalUnitVersion.text_version_id)
            .where(LegalUnitVersion.id == unit_version_id, LegalUnitVersion.unit_id == unit.id)
        ).first()
        if pair is None:
            return None
        shown_uv, shown_tv = pair[0], pair[1]
        archived = current.unit_version is None or shown_uv.id != current.unit_version.id

    freshness = fresh.for_unit(s, unit, current)
    if archived and shown_tv is not None:
        reason = Reason(
            "niepotwierdzona",
            "wersja_archiwalna",
            "To nie jest najnowsza wersja tego przepisu",
            f"Pokazujemy brzmienie z {shown_tv.journal_display}, zapisane w systemie {words_date(shown_uv.recorded_at.date()) if shown_uv else ''}. "
            "Najnowszą wersję otworzysz linkiem pod tytułem.",
        )
        reasons = [reason, *freshness.reasons]
        worst = max(reasons, key=lambda r: SEVERITY[r.status])
        freshness = Freshness(
            worst.status, worst.date, None, reasons, freshness.confirmed_at, freshness.confirmation_scope
        )

    explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    expl_out: o.ExplanationOut | None = None
    expl_status = "brak"
    expl_versions: list[o.ExplanationVersionOut] = []
    if explanation is not None:
        ever = [v for v in explanation.versions if v.state in (S.OPUBLIKOWANY, S.ZAWIESZONY, S.COFNIETY)]
        expl_versions = [
            o.ExplanationVersionOut(
                id=v.id,
                version_no=v.version_no,
                state=v.state,
                published_at=v.published_at,
                verified_on=v.verified_on,
                permalink=f"/przepis/{unit.slug}?objasnienie={v.id}",
            )
            for v in sorted(ever, key=lambda v: v.version_no, reverse=True)
        ]
        chosen = (
            next((v for v in ever if v.id == explanation_version_id), None)
            if explanation_version_id
            else None
        )
        if chosen is None and archived and shown_uv is not None:
            chosen = max(
                (v for v in ever if v.based_on_unit_version_id == shown_uv.id),
                key=lambda v: v.version_no,
                default=None,
            )
        if chosen is None and not archived:
            chosen = public_version(explanation.versions)
        if chosen is not None:
            expl_status = {
                S.OPUBLIKOWANY: "opublikowane",
                S.ZAWIESZONY: "zawieszone",
                S.COFNIETY: "cofniete",
            }[chosen.state]  # type: ignore[index]
            expl_out = _explanation_out(s, unit, chosen) if chosen.state != S.COFNIETY else None

    tv = shown_tv
    # Bez przyjętego tekstu metryka wskazuje tekst z ELI czekający na kontrolę — tam jest oficjalne brzmienie.
    source = tv or fresh.pending_text(s, act.id, None)
    journal = source.journal_display if source else "—"
    citation = o.CitationOut(
        act=act.citation_name,
        journal=journal,
        unit=unit.label,
        as_of=source.legal_status_date if source else None,
        eli=(source.source_eli if source and source.source_eli else act.eli),
        url=eli_url(source.source_eli if source and source.source_eli else act.eli),
        text=", ".join(x for x in (act.citation_name, journal, unit.label) if x),
    )

    versions = []
    for uv, t in s.execute(
        select(LegalUnitVersion, LegalTextVersion)
        .join(LegalTextVersion, LegalTextVersion.id == LegalUnitVersion.text_version_id)
        .where(LegalUnitVersion.unit_id == unit.id, LegalTextVersion.review_state == TextReview.ZAAKCEPTOWANY)
        .order_by(LegalTextVersion.recorded_at.desc(), LegalTextVersion.id.desc())
    ).all():
        versions.append(
            o.VersionOut(
                unit_version_id=uv.id,
                journal=t.journal_display,
                text_type=o.as_text_type(t.text_type) or "nierozpoznany",
                legal_status_date=t.legal_status_date,
                recorded_at=uv.recorded_at,
                is_current=current.unit_version is not None and uv.id == current.unit_version.id,
                permalink=f"/przepis/{unit.slug}/wersja/{uv.id}",
            )
        )

    return o.ProvisionOut(
        slug=unit.slug,
        unit_key=unit.unit_key,
        label=unit.label,
        display_label=f"{act.abbrev} {unit.label}",
        title=unit.title,
        act=act_ref(act),
        text_type=o.as_text_type(tv.text_type) if tv else None,
        text_note=tv.note if tv else None,
        paragraphs=[o.Paragraph(**p) for p in (shown_uv.content if shown_uv else [])],
        freshness=freshness_out(freshness),
        explanation=expl_out,
        explanation_status=cast(o.ExplanationStatus, expl_status),
        citation=citation,
        amendments=amendments_out(s, act, tv),
        validity=validity_out(s, act.id, unit.id),
        versions=versions,
        explanation_versions=expl_versions,
        illustration=unit.illustration,
        related=related_for_unit(s, unit),
        permalink=f"/przepis/{unit.slug}/wersja/{shown_uv.id}" if shown_uv else f"/przepis/{unit.slug}",
        is_archived_version=archived,
        current_url=f"/przepis/{unit.slug}",
    )


def provision_summary(s: Session, unit: LegalUnit) -> o.ProvisionSummary:
    act = s.get(LegalAct, unit.act_id)
    assert act is not None
    ut = fresh.unit_text(s, unit)
    explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    pv = public_version(explanation.versions) if explanation else None
    return o.ProvisionSummary(
        slug=unit.slug,
        title=unit.title,
        display_label=f"{act.abbrev} {unit.label}",
        act=act_ref(act),
        text_type=o.as_text_type(ut.text_version.text_type) if ut.text_version else None,
        freshness=freshness_out(fresh.for_unit(s, unit, ut)),
        has_explanation=bool(pv and pv.state == S.OPUBLIKOWANY),
        url=f"/przepis/{unit.slug}",
    )


def text_version_out(tv: LegalTextVersion) -> o.TextVersionOut:
    return o.TextVersionOut(
        id=tv.id,
        text_type=o.as_text_type(tv.text_type) or "nierozpoznany",
        journal=tv.journal_display,
        source_eli=tv.source_eli,
        legal_status_date=tv.legal_status_date,
        review_state=tv.review_state,
        parse_quality=tv.parse_quality,
        note=tv.note,
        origin=tv.origin,
        recorded_at=tv.recorded_at,
    )


def act_out(s: Session, act: LegalAct) -> o.ActOut:
    tv = fresh.current_text(s, act.id)
    units = s.scalars(
        select(LegalUnit)
        .where(LegalUnit.act_id == act.id, LegalUnit.featured.is_(True))
        .order_by(LegalUnit.id)
    ).all()
    return o.ActOut(
        slug=act.slug,
        eli=act.eli,
        short_title=act.short_title,
        abbrev=act.abbrev,
        title=act.title,
        act_kind=act.act_kind,
        area=act.area,
        in_mvp=act.in_mvp,
        official_url=act.official_url,
        text_format=act.text_format,
        owner=act.owner,
        manifest_verified_on=act.manifest_verified_on,
        relations=act.relations or [],
        current_text=text_version_out(tv) if tv else None,
        freshness=freshness_out(fresh.for_act(s, act)),
        amendments=amendments_out(s, act, tv),
        validity=validity_out(s, act.id, None),
        last_sync_ok=fresh.last_sync_ok(s, act.id),
        units=[unit_ref(u, act) for u in units],
    )


def _to_check(s: Session, nodes: list[Any], key: str) -> dict[str, list[o.ToCheckOut]]:
    """Dla każdej odpowiedzi prowadzącej do wyniku „poza zakresem”: pasujące punkty art. 29 (4.2)."""
    out: dict[str, list[o.ToCheckOut]] = {}
    for node in nodes:
        for opt in node.options or []:
            if opt.get("next") != key or opt["label"] in out:
                continue
            found = [
                o.ToCheckOut(
                    unit_slug=x.unit_slug,
                    label=x.label,
                    intro=x.intro,
                    paragraphs=[o.Paragraph(**para) for para in x.paragraphs],
                    url=f"/przepis/{x.unit_slug}",
                    rule=x.rule,
                )
                for x in to_check(s, opt["label"])
            ]
            if found:
                out[opt["label"]] = found
    return out


def tree_out(s: Session, tree: DecisionTree) -> o.TreeOut | None:
    tv = public_version(tree.versions)
    if tv is None or tv.state != S.OPUBLIKOWANY:
        return None
    flags = active_flags(s, "decision_tree_node_version", [n.id for n in tv.nodes])
    nodes: dict[str, o.TreeNodeOut] = {}
    for n in tv.nodes:
        units = unit_refs(s, n.unit_slugs or [])
        status = None
        status_date = None
        status_eff = None
        if n.kind == "wynik" and units:
            worst: Freshness | None = None
            for ref in units:
                unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == ref.slug))
                assert unit is not None
                f = fresh.for_unit(s, unit)
                if worst is None or SEVERITY[f.status] > SEVERITY[worst.status]:
                    worst = f
            if worst is not None:
                status, status_date, status_eff = worst.status, worst.date, worst.effective_date
        flag = flags.get(n.id)
        nodes[n.node_key] = o.TreeNodeOut(
            key=n.node_key,
            kind=cast(o.NodeKind, n.kind),
            step_label=n.step_label,
            question=n.question,
            help=n.help,
            options=[o.TreeOption(**opt) for opt in n.options or []],
            result_title=n.result_title,
            result_body=n.result_body,
            outcome=n.outcome,
            basis=n.basis_label,
            units=units,
            links=n.links or [],
            status=o.as_status(status) if status else None,
            status_date=status_date,
            status_effective_date=status_eff,
            suspended=flag is not None,
            suspended_reason=flag.reason if flag else None,
            to_check=_to_check(s, tv.nodes, n.node_key) if n.outcome == "poza_zakresem" else {},
        )
    return o.TreeOut(
        slug=tree.slug,
        title=tv.title,
        intro=tv.intro,
        scope_note=tv.scope_note,
        root=tv.root_node_key,
        nodes=nodes,
        version_id=tv.id,
        version_no=tv.version_no,
        is_demo=tv.is_demo,
        verified_on=tv.verified_on,
        state=tv.state,
    )


def guide_out(s: Session, guide: Guide) -> o.GuideOut | None:
    gv = public_version(guide.versions)
    if gv is None or gv.state != S.OPUBLIKOWANY:
        return None
    steps = []
    for st in gv.steps:
        refs = unit_refs(s, [st["unit"]]) if st.get("unit") else []
        steps.append(
            o.GuideStepOut(
                title=st["title"],
                who=st.get("who"),
                body=st["body"],
                documents=st.get("documents") or [],
                basis=st.get("basis"),
                unit=refs[0] if refs else None,
                link=st.get("link"),
                illustration=st.get("illustration"),
            )
        )
    return o.GuideOut(
        slug=guide.slug,
        title=gv.title,
        summary=gv.summary,
        caveat=gv.caveat,
        steps=steps,
        units=unit_refs(s, gv.unit_slugs or []),
        is_demo=gv.is_demo,
        verified_on=gv.verified_on,
        state=gv.state,
        version_id=gv.id,
        version_no=gv.version_no,
    )


def glossary_out(s: Session) -> list[o.GlossaryTermOut]:
    terms = s.scalars(select(GlossaryTerm)).all()
    labels: dict[str, str] = {}
    published = []
    for term in terms:
        tv = public_version(term.versions)
        if tv is not None and tv.state == S.OPUBLIKOWANY:
            labels[term.slug] = tv.term_label
            published.append((term, tv))
    out = []
    for term, tv in sorted(published, key=lambda p: p[1].term_label.lower()):
        out.append(
            o.GlossaryTermOut(
                slug=term.slug,
                term=tv.term_label,
                definition=tv.definition,
                basis=tv.basis_label,
                units=unit_refs(s, tv.unit_slugs or []),
                see_also=[{"slug": x, "term": labels[x]} for x in (tv.see_also or []) if x in labels],
                illustration=tv.illustration,
                is_demo=tv.is_demo,
                verified_on=tv.verified_on,
                state=tv.state,
                version_id=tv.id,
            )
        )
    return out
