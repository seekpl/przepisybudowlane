"""Ładowanie manifestu aktów i treści startowych. Idempotentne: drugi przebieg niczego nie dubluje.

Treści redakcyjne przechodzą przez ten sam obieg co w panelu redakcji (z kontami demonstracyjnymi),
więc historia przejść jest kompletna, a zasada „autor nie zatwierdza własnej treści” obowiązuje także tu.
Istniejących wersji redakcyjnych seed nie nadpisuje — zmiany treści robi się w panelu, nie w YAML-u.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Editor
from app.history import record
from app.models import (
    DecisionTree,
    DecisionTreeNodeVersion,
    DecisionTreeVersion,
    EditorialState,
    Explanation,
    ExplanationVersion,
    GlossaryTerm,
    GlossaryTermVersion,
    Guide,
    GuideVersion,
    LegalAct,
    LegalTextVersion,
    LegalUnit,
    LegalUnitVersion,
    LegalValidityInterval,
    SearchSynonym,
    SourceVerification,
    TextReview,
)
from app.modules.editorial.workflow import transition
from app.modules.freshness.service import unit_text
from app.modules.parser.units import content_hash
from app.modules.registry.units import unit_label, unit_slug

SEED_DIR = Path(__file__).resolve().parents[3] / "seed"
ACTOR = "seed"
DEMO_AUTHOR = Editor("demo-redaktor", frozenset({"redaktor"}), "")
DEMO_REVIEWER = Editor("demo-recenzent", frozenset({"recenzent"}), "")
S = EditorialState


def _yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict)
    return data


def load_manifest(s: Session, path: Path = SEED_DIR / "manifest.yaml") -> int:
    count = 0
    for item in _yaml(path)["acts"]:
        act = s.scalar(select(LegalAct).where(LegalAct.slug == item["slug"]))
        fields = {
            k: item.get(k)
            for k in (
                "eli",
                "short_title",
                "abbrev",
                "title",
                "citation_name",
                "act_kind",
                "area",
                "in_mvp",
                "official_url",
                "text_format",
                "owner",
                "manifest_verified_on",
                "relations",
            )
        }
        fields["title"] = " ".join(str(fields["title"]).split())
        fields["citation_name"] = " ".join(str(fields["citation_name"]).split())
        if act is None:
            act = LegalAct(slug=item["slug"], **fields)
            s.add(act)
            s.flush()
            record(s, actor=ACTOR, entity="legal_act", entity_id=act.id, action="dodano_do_manifestu")
        else:
            changed = {k: v for k, v in fields.items() if getattr(act, k) != v}
            for k, v in changed.items():
                setattr(act, k, v)
            if changed:
                record(
                    s,
                    actor=ACTOR,
                    entity="legal_act",
                    entity_id=act.id,
                    action="zmieniono_manifest",
                    pola=sorted(changed),
                )
        count += 1
    return count


def _act(s: Session, slug: str) -> LegalAct:
    act = s.scalar(select(LegalAct).where(LegalAct.slug == slug))
    if act is None:
        raise ValueError(f"Akt {slug!r} nie jest w manifeście")
    return act


def _unit(s: Session, act: LegalAct, key: str) -> LegalUnit:
    unit = s.scalar(select(LegalUnit).where(LegalUnit.act_id == act.id, LegalUnit.unit_key == key))
    if unit is None:
        raise ValueError(f"Brak jednostki {key} w akcie {act.slug}")
    return unit


def _publish(s: Session, version: Any) -> None:
    transition(s, version, S.RECENZJA, DEMO_AUTHOR)
    transition(s, version, S.ZATWIERDZONY, DEMO_REVIEWER, "Treść demonstracyjna — bez recenzji prawnej")
    transition(s, version, S.OPUBLIKOWANY, DEMO_REVIEWER)


def _text_versions(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        act = _act(s, item["act"])
        tv = s.scalar(
            select(LegalTextVersion).where(
                LegalTextVersion.act_id == act.id,
                LegalTextVersion.origin == "redakcja",
                LegalTextVersion.journal_display == item["journal_display"],
                LegalTextVersion.text_type == item["text_type"],
            )
        )
        if tv is None:
            tv = LegalTextVersion(
                act_id=act.id,
                text_type=item["text_type"],
                source_eli=item.get("source_eli"),
                journal_display=item["journal_display"],
                legal_status_date=item.get("legal_status_date"),
                incorporated=item.get("incorporated") or [],
                origin="redakcja",
                review_state=TextReview.ZAAKCEPTOWANY,
                reviewed_by=ACTOR,
                note=" ".join(str(item.get("note") or "").split()) or None,
            )
            s.add(tv)
            s.flush()
            record(s, actor=ACTOR, entity="legal_text_version", entity_id=tv.id, action="tekst_redakcji")
        for u in item["units"]:
            unit = s.scalar(
                select(LegalUnit).where(LegalUnit.act_id == act.id, LegalUnit.unit_key == u["key"])
            )
            if unit is None:
                unit = LegalUnit(
                    act_id=act.id,
                    unit_key=u["key"],
                    label=unit_label(u["key"]),
                    slug=unit_slug(act.slug, u["key"]),
                )
                s.add(unit)
            unit.title = u.get("title") or unit.title
            unit.featured = bool(u.get("featured", unit.featured))
            unit.illustration = u.get("illustration") or unit.illustration
            s.flush()
            content = [{"unit": p["unit"], "text": " ".join(str(p["text"]).split())} for p in u["content"]]
            exists = s.scalar(
                select(LegalUnitVersion).where(
                    LegalUnitVersion.unit_id == unit.id, LegalUnitVersion.text_version_id == tv.id
                )
            )
            if exists is None:
                s.add(
                    LegalUnitVersion(
                        unit_id=unit.id,
                        text_version_id=tv.id,
                        content=content,
                        content_hash=content_hash(content),
                    )
                )
    s.flush()


def _validity(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        act = _act(s, item["act"])
        unit = _unit(s, act, item["unit"]) if item.get("unit") else None
        unit_cond = (
            LegalValidityInterval.unit_id == unit.id if unit else LegalValidityInterval.unit_id.is_(None)
        )
        exists = s.scalar(
            select(LegalValidityInterval).where(
                LegalValidityInterval.act_id == act.id,
                unit_cond,
                LegalValidityInterval.kind == item["kind"],
                LegalValidityInterval.valid_from == item.get("valid_from"),
                LegalValidityInterval.source == "redakcja",
            )
        )
        if exists is None:
            s.add(
                LegalValidityInterval(
                    act_id=act.id,
                    unit_id=unit.id if unit else None,
                    kind=item["kind"],
                    valid_from=item.get("valid_from"),
                    valid_to=item.get("valid_to"),
                    basis=item.get("basis"),
                    title=item.get("title"),
                    description=" ".join(str(item.get("description") or "").split()) or None,
                    source="redakcja",
                    recorded_by=ACTOR,
                )
            )


def _verifications(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        act = _act(s, item["act"])
        unit = _unit(s, act, item["unit"]) if item.get("unit") else None
        at = item["verified_at"]
        at = at if isinstance(at, datetime) else datetime.fromisoformat(str(at))
        exists = s.scalar(
            select(SourceVerification).where(
                SourceVerification.act_id == act.id, SourceVerification.verified_at == at
            )
        )
        if exists is None:
            s.add(
                SourceVerification(
                    act_id=act.id,
                    unit_id=unit.id if unit else None,
                    verified_at=at,
                    verified_by=item["verified_by"],
                    method=item["method"],
                    scope=item["scope"],
                )
            )


def _explanations(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        unit = _unit(s, _act(s, item["act"]), item["unit"])
        explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
        if explanation is None:
            explanation = Explanation(unit_id=unit.id)
            s.add(explanation)
            s.flush()
        if explanation.versions:
            continue
        current = unit_text(s, unit).unit_version
        version = ExplanationVersion(
            explanation_id=explanation.id,
            version_no=1,
            title=item.get("title"),
            body=item["body"].strip(),
            author=DEMO_AUTHOR.name,
            is_demo=True,
            based_on_unit_version_id=current.id if current else None,
        )
        s.add(version)
        s.flush()
        _publish(s, version)


def _glossary(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        term = s.scalar(select(GlossaryTerm).where(GlossaryTerm.slug == item["slug"]))
        if term is None:
            term = GlossaryTerm(slug=item["slug"])
            s.add(term)
            s.flush()
        if term.versions:
            continue
        version = GlossaryTermVersion(
            term_id=term.id,
            version_no=1,
            term_label=item["term"],
            definition=" ".join(item["definition"].split()),
            basis_label=item.get("basis"),
            unit_slugs=item.get("units") or [],
            see_also=item.get("see_also") or [],
            illustration=item.get("illustration"),
            author=DEMO_AUTHOR.name,
            is_demo=True,
        )
        s.add(version)
        s.flush()
        _publish(s, version)


def _guides(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        guide = s.scalar(select(Guide).where(Guide.slug == item["slug"]))
        if guide is None:
            guide = Guide(slug=item["slug"])
            s.add(guide)
            s.flush()
        if guide.versions:
            continue
        steps = [
            {
                "title": st["title"],
                "who": st.get("who"),
                "body": " ".join(st["body"].split()),
                "documents": st.get("documents") or [],
                "basis": st.get("basis"),
                "unit": st.get("unit"),
                "link": st.get("link"),
                "illustration": st.get("illustration"),
            }
            for st in item["steps"]
        ]
        version = GuideVersion(
            guide_id=guide.id,
            version_no=1,
            title=item["title"],
            summary=" ".join(item["summary"].split()),
            caveat=" ".join(str(item.get("caveat") or "").split()) or None,
            steps=steps,
            unit_slugs=item.get("units") or [],
            author=DEMO_AUTHOR.name,
            is_demo=True,
        )
        s.add(version)
        s.flush()
        _publish(s, version)


def _trees(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        tree = s.scalar(select(DecisionTree).where(DecisionTree.slug == item["slug"]))
        if tree is None:
            tree = DecisionTree(slug=item["slug"])
            s.add(tree)
            s.flush()
        if tree.versions:
            continue
        version = DecisionTreeVersion(
            tree_id=tree.id,
            version_no=1,
            title=item["title"],
            intro=" ".join(item["intro"].split()),
            scope_note=" ".join(str(item.get("scope_note") or "").split()) or None,
            root_node_key=item["root"],
            author=DEMO_AUTHOR.name,
            is_demo=True,
        )
        s.add(version)
        s.flush()
        keys = {n["key"] for n in item["nodes"]}
        for n in item["nodes"]:
            for opt in n.get("options") or []:
                if opt["next"] not in keys:
                    raise ValueError(
                        f"Kreator {tree.slug}: opcja „{opt['label']}” prowadzi do nieistniejącego węzła {opt['next']}"
                    )
            s.add(
                DecisionTreeNodeVersion(
                    tree_version_id=version.id,
                    node_key=n["key"],
                    kind=n["kind"],
                    step_label=n.get("step") or "Wynik",
                    question=n.get("question"),
                    help=n.get("help"),
                    options=n.get("options") or [],
                    result_title=n.get("title"),
                    result_body=" ".join(str(n.get("body") or "").split()) or None,
                    outcome=n.get("outcome"),
                    basis_label=n.get("basis"),
                    unit_slugs=n.get("units") or [],
                    links=n.get("links") or [],
                )
            )
        s.flush()
        _publish(s, version)


def _synonyms(s: Session, items: list[dict[str, Any]]) -> None:
    for item in items:
        syn = s.scalar(select(SearchSynonym).where(SearchSynonym.term == item["term"]))
        if syn is None:
            s.add(SearchSynonym(term=item["term"], expansions=item["expansions"], note=item.get("note")))
        else:
            syn.expansions, syn.note = item["expansions"], item.get("note")


def load_content(s: Session, path: Path = SEED_DIR / "content.yaml") -> None:
    data = _yaml(path)
    _text_versions(s, data.get("text_versions") or [])
    _validity(s, data.get("validity") or [])
    _verifications(s, data.get("verifications") or [])
    _explanations(s, data.get("explanations") or [])
    _glossary(s, data.get("glossary") or [])
    _guides(s, data.get("guides") or [])
    _trees(s, data.get("trees") or [])
    _synonyms(s, data.get("synonyms") or [])
    s.flush()


def seed_all(s: Session) -> None:
    from app.modules.search.service import rebuild_index

    load_manifest(s)
    load_content(s)
    rebuild_index(s)
