from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

os.environ.setdefault("PB_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/przepisy_test")
os.environ["PB_EDITOR_TOKENS"] = "anna=redaktor:tok-anna;jan=recenzent:tok-jan;ola=redaktor+recenzent:tok-ola"

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import clock
from app.cli import _migrate
from app.config import get_settings
from app.db import Base, get_engine, get_sessionmaker
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "eli"
NOW = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Schemat z migracji (nie z metadanych) — testy sprawdzają też, że migracje działają."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    _migrate()


@pytest.fixture(autouse=True)
def _clean_db() -> Iterator[None]:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    clock.set_clock(lambda: NOW)
    yield
    clock.reset_clock()


@pytest.fixture
def set_now() -> Callable[[datetime], None]:
    def _set(dt: datetime) -> None:
        clock.set_clock(lambda: dt)

    return _set


@pytest.fixture
def session() -> Iterator[Session]:
    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


# Akty, dla których syntetyczne odpowiedzi ELI mają tekst (Prawo budowlane, warunki techniczne).
SYNCED_ACTS = ("prawo-budowlane", "warunki-techniczne")


@pytest.fixture
def manifest(session: Session) -> Session:
    """Sam manifest aktów — stan przed pierwszą synchronizacją."""
    from app.modules.content.seed import load_manifest

    load_manifest(session)
    session.commit()
    return session


@pytest.fixture
def seeded(manifest: Session, make_sync) -> Session:  # type: ignore[no-untyped-def]
    """Kolejność jak na produkcji: manifest → synchronizacja z ELI (tu: odpowiedzi syntetyczne) → treści."""
    from sqlalchemy import update

    from app.models import LegalAct
    from app.modules.content.seed import load_content
    from app.modules.search.service import rebuild_index

    s = manifest
    in_mvp = dict(s.execute(select(LegalAct.slug, LegalAct.in_mvp)).all())
    s.execute(update(LegalAct).where(LegalAct.slug.not_in(SYNCED_ACTS)).values(in_mvp=False))
    s.commit()
    report = make_sync().run("seed-testowy")
    assert report.status == "sukces", report.errors
    for slug, flag in in_mvp.items():
        s.execute(update(LegalAct).where(LegalAct.slug == slug).values(in_mvp=flag))
    s.commit()
    load_content(s)
    rebuild_index(s)
    s.commit()
    return s


@pytest.fixture
def api() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def archive_dir(tmp_path: Path) -> Path:
    return tmp_path / "archive"


class FakeEli:
    """Serwer ELI z odpowiedziami z plików; trasy można nadpisać w teście (awarie, nowe brzmienia)."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, bytes, str]] = {}
        self.calls: list[str] = []
        for f in FIXTURES.glob("DU_*.json"):
            pub, year, pos = f.stem.split("_")
            self.routes[f"/eli/acts/{pub}/{year}/{pos}"] = (200, f.read_bytes(), "application/json")
        for f in FIXTURES.glob("DU_*.html"):
            pub, year, pos = f.stem.split("_")
            self.routes[f"/eli/acts/{pub}/{year}/{pos}/text.html"] = (
                200,
                f.read_bytes(),
                "text/html; charset=utf-8",
            )
        self.routes["/eli/changes/acts"] = (200, b"[]", "application/json")

    def set_json(self, path: str, data: object, status: int = 200) -> None:
        self.routes[path] = (status, json.dumps(data).encode(), "application/json")

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        if path not in self.routes:
            return httpx.Response(404, json={"error": "not found"})
        status, body, ctype = self.routes[path]
        return httpx.Response(status, content=body, headers={"content-type": ctype})


@pytest.fixture
def fake_eli() -> FakeEli:
    return FakeEli()


@pytest.fixture
def make_sync(fake_eli: FakeEli, archive_dir: Path):  # type: ignore[no-untyped-def]
    from app.modules.archive.storage import Archive
    from app.modules.eli.client import EliClient
    from app.modules.sync.service import SyncService

    def _make(**overrides):  # type: ignore[no-untyped-def]
        settings = get_settings().model_copy(update=overrides)
        client = EliClient(
            "https://api.example.test/eli",
            transport=httpx.MockTransport(fake_eli.handler),
            max_retries=1,
            backoff=0,
            sleep=lambda _: None,
        )
        return SyncService(get_sessionmaker(), client, Archive(archive_dir), settings)

    return _make


def only_act(session: Session, slug: str) -> None:
    """Zostawia w manifeście MVP tylko jeden akt — testy synchronizacji dotyczą jednego aktu."""
    from sqlalchemy import update

    from app.models import LegalAct

    session.execute(update(LegalAct).where(LegalAct.slug != slug).values(in_mvp=False))
    session.commit()
