"""Tekst prawa tylko z ELI (arkusz, działania 2.1–2.3): baza, dane startowe i kolejność ładowania."""

from __future__ import annotations

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Explanation,
    ExplanationVersion,
    LegalAct,
    LegalTextVersion,
    LegalUnit,
    SourceSnapshot,
)
from app.modules.content.seed import SEED_DIR, check_no_law_text, load_content
from tests.conftest import only_act


def test_database_rejects_text_version_without_eli_snapshot(manifest: Session) -> None:
    act = manifest.scalar(select(LegalAct).where(LegalAct.slug == "prawo-budowlane"))
    manifest.add(
        LegalTextVersion(
            act_id=act.id,
            text_type="nierozpoznany",
            journal_display="wpisane ręcznie",
            origin="redakcja",
            review_state="zaakceptowany",
        )
    )
    with pytest.raises(IntegrityError):
        manifest.flush()
    manifest.rollback()


def test_database_rejects_text_version_not_from_eli(manifest: Session) -> None:
    act = manifest.scalar(select(LegalAct).where(LegalAct.slug == "prawo-budowlane"))
    snap = SourceSnapshot(
        act_id=act.id,
        url="https://example.test/tekst",
        kind="text_html",
        sha256="0" * 64,
        size_bytes=1,
        http_status=200,
        storage_key="x",
    )
    manifest.add(snap)
    manifest.flush()
    manifest.add(
        LegalTextVersion(
            act_id=act.id,
            text_type="jednolity",
            journal_display="Dz.U. 2026 poz. 524",
            snapshot_id=snap.id,
            origin="redakcja",
            review_state="zaakceptowany",
        )
    )
    with pytest.raises(IntegrityError):
        manifest.flush()
    manifest.rollback()


def test_snapshot_needs_sha256(manifest: Session) -> None:
    manifest.add(
        SourceSnapshot(
            url="https://example.test/x",
            kind="text_html",
            sha256="nie-suma",
            size_bytes=1,
            http_status=200,
            storage_key="x",
        )
    )
    with pytest.raises(IntegrityError):
        manifest.flush()
    manifest.rollback()


def test_seed_data_contains_no_law_text() -> None:
    """Test w CI: dane startowe odsyłają do jednostek, ale nie zawierają ich brzmienia."""
    data = yaml.safe_load((SEED_DIR / "content.yaml").read_text(encoding="utf-8"))
    check_no_law_text(data)
    assert "text_versions" not in data


@pytest.mark.parametrize(
    "bad",
    [
        {"text_versions": [{"act": "prawo-budowlane"}]},
        {
            "units": [
                {"act": "prawo-budowlane", "key": "art_28", "content": [{"unit": "Art. 28.", "text": "…"}]}
            ]
        },
    ],
)
def test_loader_refuses_law_text(manifest: Session, tmp_path, bad) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "content.yaml"
    path.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="wyłącznie z synchronizacji z ELI"):
        load_content(manifest, path)


def test_content_waits_for_eli_text_and_publishes_after_sync(manifest: Session, make_sync) -> None:  # type: ignore[no-untyped-def]
    # Treści przed synchronizacją: nie ma jednostek, więc objaśnienia czekają (nic nie jest publikowane).
    load_content(manifest)
    manifest.commit()
    assert manifest.scalar(select(ExplanationVersion)) is None

    only_act(manifest, "prawo-budowlane")
    assert make_sync().run().status == "sukces"
    load_content(manifest)  # drugi przebieg dokańcza to, co czekało na tekst
    manifest.commit()
    published = manifest.scalars(
        select(ExplanationVersion).where(ExplanationVersion.state == "opublikowany")
    ).all()
    assert published and all(v.based_on_unit_version_id is not None for v in published)
    # WT nie był synchronizowany: jego objaśnienie dalej czeka, nie ma też pustej karty.
    wt_explanation = manifest.scalar(
        select(Explanation)
        .join(LegalUnit, LegalUnit.id == Explanation.unit_id)
        .join(LegalAct, LegalAct.id == LegalUnit.act_id)
        .where(LegalAct.slug == "warunki-techniczne")
    )
    assert wt_explanation is None
