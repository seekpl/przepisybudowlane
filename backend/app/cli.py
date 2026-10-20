"""Polecenia operacyjne: python -m app.cli <polecenie>.

migrate            migracje bazy (alembic upgrade head)
seed               manifest aktów + treści startowe + indeks wyszukiwarki (idempotentne)
sync               jeden przebieg synchronizacji z ELI
worker             synchronizacja co PB_SYNC_INTERVAL_MINUTES z ponawianiem; sprząta e-maile po retencji
reindex            przebudowa indeksu wyszukiwarki
eli-record ELI...  zapis surowych odpowiedzi ELI do testów kontraktu (wymaga dostępu do api.sejm.gov.pl)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from app.config import BACKEND_DIR, get_settings
from app.db import get_sessionmaker

log = logging.getLogger("przepisy")


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


def _seed() -> None:
    from app.modules.content.seed import seed_all

    with get_sessionmaker()() as s:
        seed_all(s)
        s.commit()
    log.info("Seed zakończony")


def _service():
    from app.modules.archive.storage import Archive
    from app.modules.eli.client import EliClient
    from app.modules.sync.service import SyncService

    settings = get_settings()
    client = EliClient(
        settings.eli_base_url,
        timeout=settings.eli_timeout_seconds,
        max_retries=settings.eli_max_retries,
        backoff=settings.eli_backoff_seconds,
    )
    return SyncService(get_sessionmaker(), client, Archive(settings.archive_dir), settings)


def _sync(trigger: str) -> str:
    from app.modules.search.service import rebuild_index

    report = _service().run(trigger=trigger)
    with get_sessionmaker()() as s:
        rebuild_index(s)
        s.commit()
    log.info("Synchronizacja %s: %s", report.run_id, report.status)
    for err in report.errors:
        log.warning("Błąd: %s", err)
    return report.status


def _worker() -> None:
    from app.modules.reports.service import purge_expired_emails

    settings = get_settings()
    while True:
        try:
            _sync("harmonogram")
            with get_sessionmaker()() as s:
                purged = purge_expired_emails(s)
                s.commit()
            if purged:
                log.info("Usunięto %s adresów e-mail po okresie retencji", purged)
        except Exception:
            log.exception("Przebieg synchronizacji zakończył się wyjątkiem")
        time.sleep(settings.sync_interval_minutes * 60)


def _reindex() -> None:
    from app.modules.search.service import rebuild_index

    with get_sessionmaker()() as s:
        n = rebuild_index(s)
        s.commit()
    log.info("Indeks: %s dokumentów", n)


def _record(elis: list[str], out: Path) -> None:
    """Zapisuje odpowiedzi ELI (metadane, tekst HTML) — materiał do testów kontraktu."""
    from app.modules.eli.client import EliClient, act_path

    settings = get_settings()
    client = EliClient(settings.eli_base_url, timeout=settings.eli_timeout_seconds)
    out.mkdir(parents=True, exist_ok=True)
    for eli in elis:
        meta = client.get(act_path(eli))
        name = eli.replace("/", "_")
        (out / f"{name}.json").write_bytes(meta.content)
        if json.loads(meta.content).get("textHTML"):
            (out / f"{name}.html").write_bytes(client.get(f"{act_path(eli)}/text.html").content)
        log.info("Zapisano %s", eli)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("seed")
    sub.add_parser("sync")
    sub.add_parser("worker")
    sub.add_parser("reindex")
    rec = sub.add_parser("eli-record")
    rec.add_argument("eli", nargs="+")
    rec.add_argument("--out", type=Path, default=BACKEND_DIR / "tests" / "fixtures" / "eli" / "recorded")
    args = parser.parse_args(argv)
    if args.cmd == "migrate":
        _migrate()
    elif args.cmd == "seed":
        _seed()
    elif args.cmd == "sync":
        return 0 if _sync("reczny") == "sukces" else 1
    elif args.cmd == "worker":
        _worker()
    elif args.cmd == "reindex":
        _reindex()
    elif args.cmd == "eli-record":
        _record(args.eli, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
