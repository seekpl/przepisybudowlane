"""Ładowanie manifestu aktów i treści startowych. Idempotentne: drugi przebieg niczego nie dubluje.

Treści redakcyjne przechodzą przez ten sam obieg co w panelu redakcji (z kontami demonstracyjnymi),
więc historia przejść jest kompletna, a zasada „autor nie zatwierdza własnej treści” obowiązuje także tu.
Istniejących wersji redakcyjnych seed nie nadpisuje — zmiany treści robi się w panelu, nie w YAML-u.

Tekstu prawa tu nie ma i być nie może (arkusz, działania 2.2–2.3): wstawia go synchronizacja z ELI.
Kolejność uruchomienia: ``migrate`` → ``seed --manifest-only`` → ``sync`` → ``seed``. Treści przypięte
do jednostki, której jeszcze nie ma w tekście z ELI, czekają (szkic) — kolejny ``seed`` je dokończy.
"""

from __future__ import annotations

import logging
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
    LegalUnit,
    LegalValidityInterval,
    SearchSynonym,
    SourceVerification,
)
from app.modules.editorial.workflow import transition
from app.modules.freshness.service import unit_text

log = logging.getLogger("przepisy")

SEED_DIR = Path(__file__).resolve().parents[3] / "seed"
# Klucze, pod którymi w danych startowych mógłby pojawić się tekst prawa — loader je odrzuca.
LAW_TEXT_KEYS = frozenset({"text_versions", "content", "paragraphs", "law_text"})
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


def _find_unit(s: Session, act: LegalAct, key: str) -> LegalUnit | None:
    return s.scalar(select(LegalUnit).where(LegalUnit.act_id == act.id, LegalUnit.unit_key == key))


def _units(s: Session, items: list[dict[str, Any]]) -> None:
    """Metadane redakcyjne jednostek z ELI: tytuł karty, wyróżnienie, rysunek. Tekst zostaje z ELI."""
    for item in items:
        act = _act(s, item["act"])
        unit = _find_unit(s, act, item["key"])
        if unit is None:
            log.warning(
                "Seed: %s %s — jednostki jeszcze nie ma w tekście z ELI, pomijam", act.slug, item["key"]
            )
            continue
        unit.title = item.get("title") or unit.title
        unit.featured = bool(item.get("featured", unit.featured))
        unit.illustration = item.get("illustration") or unit.illustration
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
    """Objaśnienie publikujemy tylko razem z brzmieniem z ELI, na którym je oparto."""
    for item in items:
        act = _act(s, item["act"])
        unit = _find_unit(s, act, item["unit"])
        if unit is None:
            log.warning("Seed: objaśnienie %s %s czeka na tekst z ELI", act.slug, item["unit"])
            continue
        explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
        if explanation is None:
            explanation = Explanation(unit_id=unit.id)
            s.add(explanation)
            s.flush()
        current = unit_text(s, unit).unit_version
        if not explanation.versions:
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
        else:
            version = max(explanation.versions, key=lambda v: v.version_no)
        if version.state == S.SZKIC and current is not None:
            version.based_on_unit_version_id = current.id
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


def check_no_law_text(data: Any, where: str = "content.yaml") -> None:
    """Dane startowe nie mogą zawierać tekstu prawa (arkusz, działanie 2.2) — tylko odesłania do jednostek."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in LAW_TEXT_KEYS:
                raise ValueError(
                    f"{where}: klucz {key!r} — tekst prawa pochodzi wyłącznie z synchronizacji z ELI, "
                    "nie z danych startowych"
                )
            check_no_law_text(value, f"{where}.{key}")
    elif isinstance(data, list):
        for i, value in enumerate(data):
            check_no_law_text(value, f"{where}[{i}]")


def load_content(s: Session, path: Path = SEED_DIR / "content.yaml") -> None:
    data = _yaml(path)
    check_no_law_text(data, path.name)
    _units(s, data.get("units") or [])
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
