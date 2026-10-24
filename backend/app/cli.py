"""Polecenia operacyjne: python -m app.cli <polecenie>.

migrate            migracje bazy (alembic upgrade head)
seed               manifest aktów + treści startowe + indeks wyszukiwarki (idempotentne);
                   --manifest-only: tylko manifest
sync               jeden przebieg synchronizacji z ELI; --replay KATALOG: z nagrań zamiast sieci
worker             synchronizacja co PB_SYNC_INTERVAL_MINUTES z ponawianiem; sprząta e-maile po retencji
reindex            przebudowa indeksu wyszukiwarki
search-eval        trafność wyszukiwarki: zestaw z treści, trzy warianty, porównanie z trafnosc.json
eli-record         nagranie odpowiedzi ELI dla aktów z manifestu do testów kontraktu (wymaga dostępu do
                   api.sejm.gov.pl i świeżej bazy z manifestem; w CI: workflow eli-nagrania)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import BACKEND_DIR, get_settings
from app.db import get_sessionmaker

log = logging.getLogger("przepisy")

RECORDED_DIR = BACKEND_DIR / "tests" / "fixtures" / "eli" / "recorded"


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


def _seed(manifest_only: bool = False) -> None:
    from app.modules.content.seed import load_manifest, seed_all

    with get_sessionmaker()() as s:
        if manifest_only:
            load_manifest(s)
        else:
            seed_all(s)
        s.commit()
    log.info("Seed zakończony%s", " (tylko manifest)" if manifest_only else "")


def _service(
    transport: httpx.BaseTransport | None = None,
    *,
    enforce_contract: bool = True,
    archive_dir: Path | None = None,
):
    from app.modules.archive.storage import Archive
    from app.modules.eli.client import EliClient
    from app.modules.sync.service import SyncService

    settings = get_settings()
    client = EliClient(
        settings.eli_base_url,
        timeout=settings.eli_timeout_seconds,
        max_retries=settings.eli_max_retries,
        backoff=settings.eli_backoff_seconds,
        transport=transport,
    )
    return SyncService(
        get_sessionmaker(),
        client,
        Archive(archive_dir or settings.archive_dir),
        settings,
        enforce_contract=enforce_contract,
    )


def _sync(trigger: str, replay: Path | None = None) -> str:
    from app.modules.eli.recording import ReplayTransport
    from app.modules.search.service import rebuild_index

    transport = ReplayTransport(replay, urlparse(get_settings().eli_base_url).path) if replay else None
    report = _service(transport).run(trigger="odtworzenie" if replay else trigger)
    with get_sessionmaker()() as s:
        rebuild_index(s)
        s.commit()
    log.info("Synchronizacja %s: %s", report.run_id, report.status)
    for err in report.errors:
        log.warning("Błąd: %s", err)
    if report.alarm:
        log.error("ALARM: %s", report.alarm)
    return report.status


def _worker() -> None:
    from app.modules.reports.service import purge_expired_emails

    settings = get_settings()
    while True:
        try:
            status = _sync("harmonogram")
            if settings.seed_after_sync and status in ("sukces", "czesciowy"):
                _seed()
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


def _record(out: Path) -> int:
    """Nagrywa odpowiedzi ELI, przepuszczając prawdziwą synchronizację przez transport zapisujący.

    Wymaga świeżej bazy z manifestem (migrate + seed --manifest-only). Naruszenia kontraktu nie przerywają
    nagrania — zapisujemy je w ``kontrakt.json``, a o wyniku decyduje test kontraktu na nagraniach.
    """
    import tempfile

    from sqlalchemy import select

    from app.models import SyncRun
    from app.modules.eli.recording import RecordingTransport

    with get_sessionmaker()() as s:
        if s.scalar(select(SyncRun.id).limit(1)) is not None:
            # Po wcześniejszej synchronizacji przebieg pobrałby tylko część tekstów — nagranie byłoby niepełne.
            log.error("eli-record wymaga bazy bez historii synchronizacji (migrate + seed --manifest-only)")
            return 2
    settings = get_settings()
    base_path = urlparse(settings.eli_base_url).path
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    recorder = RecordingTransport(httpx.HTTPTransport(proxy=proxy, retries=0), out, base_path)
    with tempfile.TemporaryDirectory() as archive:
        report = _service(recorder, enforce_contract=False, archive_dir=Path(archive)).run(trigger="nagranie")
    if report.status not in ("sukces", "czesciowy"):
        # Nieudany przebieg (np. brak sieci) nie nadpisuje poprzedniego nagrania.
        log.error("Nagranie nieudane (%s): %s", report.status, report.errors)
        return 1
    # Przycinamy tylko po pełnym sukcesie: przy częściowym zostają pliki aktów, których nie pobrano.
    recorder.save(prune=report.status == "sukces")
    _record_openapi(out, proxy)
    summary = {
        "status": report.status,
        "bledy": report.errors,
        "naruszenia_kontraktu": report.contract_violations,
        "pliki": len(recorder.index),
    }
    (out / "kontrakt.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    log.info("Nagrano %s odpowiedzi; status synchronizacji: %s", len(recorder.pending), report.status)
    for v in report.contract_violations:
        log.warning("Kontrakt: %s", v)
    return 0


def _search_eval(save: bool, cases_out: Path | None) -> int:
    """Trafność wyszukiwarki w trzech wariantach na zestawie zbudowanym z treści (arkusz, 5.1–5.3)."""
    from app.modules.search.evaluation import (
        BASELINE,
        build_cases,
        cases_json,
        compare_with_baseline,
        evaluate,
        save_baseline,
    )

    with get_sessionmaker()() as s:
        cases = build_cases(s)
        if cases_out is not None:
            cases_out.write_text(cases_json(cases) + "\n", encoding="utf-8")
        report = evaluate(s, cases)
        s.commit()
    log.info("Zestaw: %s przypadków %s", report["zestaw"]["przypadki"], report["zestaw"]["zrodla"])
    for name, r in report["warianty"].items():
        log.info("%-12s recall@5 %.3f  MRR@10 %.3f  %s", name, r["recall@5"], r["mrr@10"], r["wg_zrodla"])
    if report["niedostepne"]:
        log.warning("Niedostępne w tym środowisku: %s", ", ".join(report["niedostepne"]))
    log.info("Zwycięzca: %s", report["zwyciezca"])
    if save:
        save_baseline(report)
        log.info("Zapisano %s", BASELINE)
        return 0
    if not BASELINE.exists():
        log.error("Brak pomiaru odniesienia — uruchom: cli search-eval --zapisz")
        return 1
    problems = compare_with_baseline(report, json.loads(BASELINE.read_text(encoding="utf-8")))
    for problem in problems:
        log.error("Trafność: %s", problem)
    return 1 if problems else 0


OPENAPI_CANDIDATES = ("openapi/", "openapi.json", "openapi/openapi.json", "openapi.yaml", "v3/api-docs")


def _record_openapi(out: Path, proxy: str | None) -> None:
    """Specyfikacja OpenAPI ELI (arkusz, działanie 1.4): zapisujemy pierwszą odpowiedź, która jest JSON-em lub YAML-em."""
    base = get_settings().eli_base_url.rstrip("/") + "/"
    with httpx.Client(proxy=proxy, timeout=30, follow_redirects=True) as http:
        for candidate in OPENAPI_CANDIDATES:
            try:
                resp = http.get(base + candidate)
            except httpx.HTTPError as exc:
                log.warning("OpenAPI %s: %s", candidate, exc)
                continue
            ctype = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("json" in ctype or "yaml" in ctype):
                suffix = "json" if "json" in ctype else "yaml"
                (out / f"openapi.{suffix}").write_bytes(resp.content)
                log.info("Zapisano specyfikację OpenAPI z %s", base + candidate)
                return
        log.warning(
            "Nie znaleziono specyfikacji OpenAPI pod %s", ", ".join(base + c for c in OPENAPI_CANDIDATES)
        )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    seed = sub.add_parser("seed")
    seed.add_argument("--manifest-only", action="store_true")
    sync = sub.add_parser("sync")
    sync.add_argument("--replay", type=Path, help="katalog z nagraniami (eli-record) zamiast sieci")
    sub.add_parser("worker")
    sub.add_parser("reindex")
    ev = sub.add_parser("search-eval")
    ev.add_argument("--zapisz", action="store_true", help="zapisz wynik jako nowy pomiar odniesienia")
    ev.add_argument("--przypadki", type=Path, help="zapisz zestaw testowy do pliku JSON")
    rec = sub.add_parser("eli-record")
    rec.add_argument("--out", type=Path, default=RECORDED_DIR)
    args = parser.parse_args(argv)
    if args.cmd == "migrate":
        _migrate()
    elif args.cmd == "seed":
        _seed(args.manifest_only)
    elif args.cmd == "sync":
        return 0 if _sync("reczny", args.replay) == "sukces" else 1
    elif args.cmd == "search-eval":
        return _search_eval(args.zapisz, args.przypadki)
    elif args.cmd == "worker":
        _worker()
    elif args.cmd == "reindex":
        _reindex()
    elif args.cmd == "eli-record":
        return _record(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
