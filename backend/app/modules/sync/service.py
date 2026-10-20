"""Synchronizacja z ELI — idempotentna: wielokrotne uruchomienie niczego nie duplikuje ani nie gubi.

Kolejne kroki (plan, „Źródła danych, model czasu i aktualność”):
1. pobiera listę zmian od ostatniego potwierdzonego punktu synchronizacji (z zapasem),
2. dla każdego aktu z manifestu pobiera metadane, a w razie zmiany — tekst; zachowuje surową odpowiedź,
   URL, czas pobrania, SHA-256, kod odpowiedzi i wersję parsera,
3. waliduje schemat, parsuje strukturę; wynik niskiej jakości lub tylko PDF idzie do kontroli człowieka,
4. porównuje jednostki z poprzednią wersją i zapisuje różnice bez kasowania historii,
5. wykrywa nowelizacje ogłoszone po deklarowanym stanie prawnym tekstu,
6. tworzy zadania redakcyjne i zawiesza objaśnienia oraz gałęzie kreatora opisujące zmieniony tekst,
7. przesuwa checkpoint tylko po w pełni udanym przebiegu.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now, today
from app.config import Settings
from app.history import record
from app.models import (
    DecisionTreeNodeVersion,
    DecisionTreeVersion,
    DetectedAmendment,
    EditorialState,
    Explanation,
    ExplanationVersion,
    LegalAct,
    LegalTextVersion,
    LegalUnit,
    LegalUnitVersion,
    LegalValidityInterval,
    SourceFetch,
    SourceSnapshot,
    SyncCheckpoint,
    SyncRun,
    SyncStatus,
    TaskKind,
    TextReview,
    TextType,
    ValidityKind,
)
from app.modules.archive.storage import Archive
from app.modules.editorial import tasks
from app.modules.editorial.flags import flag_content
from app.modules.editorial.workflow import system_suspend
from app.modules.eli.client import EliClient, EliError, act_path
from app.modules.eli.schemas import ActMetadata, ChangeEntry
from app.modules.freshness.engine import Amendment, is_later_than
from app.modules.parser.units import parse_units
from app.modules.registry.units import unit_slug

ACTOR = "system:synchronizacja"
SOURCE = "eli"


class SyncActError(Exception):
    pass


@dataclass
class Fetched:
    snapshot: SourceSnapshot
    content: bytes
    is_new: bool


@dataclass
class ActOutcome:
    act: str
    ok: bool
    new_text_version: bool = False
    changed_units: int = 0
    new_amendments: int = 0
    error: str | None = None


@dataclass
class SyncReport:
    run_id: int
    status: str
    outcomes: list[ActOutcome] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


class SyncService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        client: EliClient,
        archive: Archive,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.client = client
        self.archive = archive
        self.settings = settings
        self._run_id: int | None = None

    # --- przebieg ----------------------------------------------------------------------

    def run(self, trigger: str = "manual") -> SyncReport:
        with self.session_factory() as s:
            checkpoint = s.get(SyncCheckpoint, SOURCE)
            since = (
                checkpoint.last_success_at - timedelta(hours=self.settings.sync_overlap_hours)
                if checkpoint
                else None
            )
            run = SyncRun(trigger=trigger, since=since, status=SyncStatus.W_TOKU)
            s.add(run)
            s.commit()
            self._run_id = run.id
            started_at = run.started_at
            acts = s.scalars(select(LegalAct).where(LegalAct.in_mvp.is_(True)).order_by(LegalAct.id)).all()
            act_ids = [a.id for a in acts]

        report = SyncReport(run_id=self._run_id, status=SyncStatus.W_TOKU)
        changed: set[str] | None = None
        if since is not None:
            try:
                changed = self._changed_since(since)
            except SyncActError as exc:
                # Bez listy zmian odświeżamy wszystko — wolniej, ale bez ryzyka przeoczenia.
                report.errors.append({"etap": "lista zmian", "blad": str(exc)})

        for act_id in act_ids:
            outcome = self._sync_act(act_id, changed)
            report.outcomes.append(outcome)
            if not outcome.ok:
                report.errors.append({"akt": outcome.act, "blad": outcome.error})

        failed = [o for o in report.outcomes if not o.ok]
        if not report.outcomes:
            status = SyncStatus.SUKCES if not report.errors else SyncStatus.BLAD
        elif not failed:
            status = SyncStatus.SUKCES if not report.errors else SyncStatus.CZESCIOWY
        elif len(failed) == len(report.outcomes):
            status = SyncStatus.BLAD
        else:
            status = SyncStatus.CZESCIOWY
        report.status = status

        with self.session_factory() as s:
            finished = s.get(SyncRun, self._run_id)
            assert finished is not None
            finished.status = status
            finished.finished_at = now()
            finished.errors = report.errors
            finished.stats = {
                "akty": len(report.outcomes),
                "nowe_wersje_tekstu": sum(o.new_text_version for o in report.outcomes),
                "zmienione_jednostki": sum(o.changed_units for o in report.outcomes),
                "nowe_nowelizacje": sum(o.new_amendments for o in report.outcomes),
            }
            if status == SyncStatus.SUKCES:
                cp = s.get(SyncCheckpoint, SOURCE)
                if cp is None:
                    s.add(SyncCheckpoint(source=SOURCE, last_success_at=started_at, run_id=finished.id))
                else:
                    cp.last_success_at = started_at
                    cp.run_id = finished.id
            else:
                for err in report.errors:
                    tasks.ensure_task(
                        s,
                        kind=TaskKind.AWARIA_SYNCHRONIZACJI,
                        dedupe_key=f"awaria:{err.get('akt') or err.get('etap')}:{today().isoformat()}",
                        title=f"Synchronizacja nie powiodła się: {err.get('akt') or err.get('etap')}",
                        details=err,
                    )
            record(
                s, actor=ACTOR, entity="sync_run", entity_id=finished.id, action="zakonczono", status=status
            )
            s.commit()
        return report

    def _changed_since(self, since: Any) -> set[str]:
        fetched = self._fetch(
            "/changes/acts",
            kind="changes",
            act_id=None,
            params={"since": since.strftime("%Y-%m-%dT%H:%M:%S")},
        )
        try:
            raw = json.loads(fetched.content)
            items = raw.get("items", raw) if isinstance(raw, dict) else raw
            return {ChangeEntry.model_validate(item).eli for item in items}
        except (ValueError, ValidationError, AttributeError, TypeError) as exc:
            raise SyncActError(f"Niepoprawna lista zmian: {exc}") from exc

    def _sync_act(self, act_id: int, changed: set[str] | None) -> ActOutcome:
        with self.session_factory() as s:
            act = s.get(LegalAct, act_id)
            assert act is not None
            outcome = ActOutcome(act=act.slug, ok=False)
            try:
                self._process_act(s, act, changed, outcome)
                record(
                    s,
                    actor=ACTOR,
                    entity="legal_act",
                    entity_id=act.id,
                    action="synchronizacja_ok",
                    run_id=self._run_id,
                )
                s.commit()
                outcome.ok = True
            except SyncActError as exc:
                s.rollback()
                outcome.error = str(exc)
            return outcome

    # --- pobieranie i archiwum -------------------------------------------------------------

    def _fetch(
        self, path: str, *, kind: str, act_id: int | None, params: dict[str, str] | None = None
    ) -> Fetched:
        """Pobiera zasób, archiwizuje go i od razu zapisuje ślad pobrania — także nieudanego."""
        url = self.client.url(path)
        try:
            resp = self.client.get(path, params=params)
        except EliError as exc:
            with self.session_factory() as s:
                s.add(
                    SourceFetch(
                        sync_run_id=self._run_id,
                        act_id=act_id,
                        url=exc.url,
                        kind=kind,
                        http_status=exc.status,
                        ok=False,
                        error=str(exc),
                    )
                )
                s.commit()
            raise SyncActError(f"{kind}: {exc}") from exc

        digest, key = self.archive.put(resp.content)
        with self.session_factory() as s:
            snap = s.scalar(
                select(SourceSnapshot).where(SourceSnapshot.url == resp.url, SourceSnapshot.sha256 == digest)
            )
            is_new = snap is None
            if snap is None:
                snap = SourceSnapshot(
                    act_id=act_id,
                    url=resp.url,
                    kind=kind,
                    sha256=digest,
                    size_bytes=len(resp.content),
                    content_type=resp.content_type,
                    http_status=resp.status,
                    storage_key=key,
                )
                s.add(snap)
                s.flush()
            s.add(
                SourceFetch(
                    sync_run_id=self._run_id,
                    act_id=act_id,
                    url=resp.url or url,
                    kind=kind,
                    http_status=resp.status,
                    snapshot_id=snap.id,
                    ok=True,
                    duration_ms=resp.duration_ms,
                )
            )
            s.commit()
            s.expunge(snap)
        return Fetched(snapshot=snap, content=resp.content, is_new=is_new)

    def _metadata(self, eli: str, *, kind: str, act_id: int) -> tuple[Fetched, ActMetadata]:
        fetched = self._fetch(act_path(eli), kind=kind, act_id=act_id)
        try:
            meta = ActMetadata.model_validate_json(fetched.content)
        except ValidationError as exc:
            raise SyncActError(f"Metadane {eli} nie przeszły walidacji: {exc.error_count()} błędów") from exc
        if meta.eli != eli:
            raise SyncActError(f"ELI zwróciło inny akt ({meta.eli}) niż żądany ({eli})")
        return fetched, meta

    # --- przetwarzanie aktu ----------------------------------------------------------------

    def _process_act(self, s: Session, act: LegalAct, changed: set[str] | None, outcome: ActOutcome) -> None:
        meta_fetch, meta = self._metadata(act.eli, kind="metadata", act_id=act.id)
        self._record_validity(s, act, meta)

        tj_refs = sorted(meta.refs("consolidated_texts"), key=lambda r: (r.on or date.min, r.id))
        if tj_refs:
            source_eli = tj_refs[-1].id
            src_fetch, src_meta = self._metadata(source_eli, kind="metadata_tj", act_id=act.id)
            text_type = TextType.JEDNOLITY
            status_date = src_meta.legal_status_date
        else:
            source_eli, src_fetch, src_meta = act.eli, meta_fetch, meta
            text_type = TextType.OGLOSZONY
            status_date = meta.legal_status_date or meta.promulgation

        current = self._current_text(s, act.id)
        needs_text = (
            current is None
            or current.source_eli != source_eli
            or meta_fetch.is_new
            or src_fetch.is_new
            or (changed is not None and (act.eli in changed or source_eli in changed))
        )
        if needs_text:
            new_version = self._ingest_text(s, act, src_meta, text_type, status_date)
            if new_version is not None:
                outcome.new_text_version = True
                if new_version.review_state == TextReview.ZAAKCEPTOWANY and current is not None:
                    outcome.changed_units = self._diff_units(s, act, current, new_version)

        if status_date is not None:
            outcome.new_amendments = self._detect_amendments(s, act, meta, status_date)

    def _record_validity(self, s: Session, act: LegalAct, meta: ActMetadata) -> None:
        """Zapisuje przedział obowiązywania z metadanych tylko wtedy, gdy się zmienił (bez duplikatów)."""
        if meta.repeal_date or meta.in_force == "NOT_IN_FORCE":
            kind, valid_from = ValidityKind.UTRACIL_MOC, meta.repeal_date
        elif meta.in_force == "IN_FORCE":
            kind, valid_from = ValidityKind.OBOWIAZUJE, meta.entry_into_force or meta.valid_from
        else:
            return
        last = s.scalar(
            select(LegalValidityInterval)
            .where(
                LegalValidityInterval.act_id == act.id,
                LegalValidityInterval.unit_id.is_(None),
                LegalValidityInterval.source == SOURCE,
            )
            .order_by(LegalValidityInterval.id.desc())
        )
        if last is not None and last.kind == kind and last.valid_from == valid_from:
            return
        s.add(
            LegalValidityInterval(
                act_id=act.id,
                kind=kind,
                valid_from=valid_from,
                source=SOURCE,
                recorded_by=ACTOR,
                basis=f"Metadane ELI {act.eli} (status: {meta.status})",
                supersedes_id=last.id if last else None,
            )
        )

    def _current_text(self, s: Session, act_id: int) -> LegalTextVersion | None:
        return s.scalar(
            select(LegalTextVersion)
            .where(
                LegalTextVersion.act_id == act_id, LegalTextVersion.review_state == TextReview.ZAAKCEPTOWANY
            )
            .order_by(LegalTextVersion.recorded_at.desc(), LegalTextVersion.id.desc())
        )

    def _ingest_text(
        self, s: Session, act: LegalAct, src: ActMetadata, text_type: TextType, status_date: date | None
    ) -> LegalTextVersion | None:
        base = act_path(src.eli)
        if src.text_html:
            fetched = self._fetch(f"{base}/text.html", kind="text_html", act_id=act.id)
        elif src.text_pdf:
            fetched = self._fetch(f"{base}/text.pdf", kind="text_pdf", act_id=act.id)
        else:
            raise SyncActError(f"ELI nie udostępnia tekstu {src.eli} ani w HTML, ani w PDF")

        existing = s.scalar(
            select(LegalTextVersion).where(
                LegalTextVersion.act_id == act.id, LegalTextVersion.snapshot_id == fetched.snapshot.id
            )
        )
        if existing is not None:
            return None

        version = LegalTextVersion(
            act_id=act.id,
            text_type=text_type,
            source_eli=src.eli,
            journal_display=src.journal_display,
            legal_status_date=status_date,
            published_on=src.promulgation,
            snapshot_id=fetched.snapshot.id,
            origin=SOURCE,
            incorporated=[],
        )
        if not src.text_html:
            version.review_state = TextReview.DO_KONTROLI
            version.note = "Tekst dostępny tylko w PDF — wymaga kontroli człowieka przed publikacją."
            s.add(version)
            s.flush()
            tasks.ensure_task(
                s,
                kind=TaskKind.KONTROLA_PARSERA,
                act_id=act.id,
                dedupe_key=f"kontrola:{act.id}:{fetched.snapshot.sha256}",
                title=f"{act.short_title}: tekst {src.journal_display} tylko w PDF — sprawdź i wprowadź strukturę",
                details={"tekst": src.eli, "wersja_tekstu": version.id},
            )
            return version

        result = parse_units(fetched.content.decode("utf-8", errors="replace"))
        version.parser_version = result.parser_version
        version.parse_quality = result.quality
        accepted = result.quality >= self.settings.parser_quality_threshold and bool(result.units)
        version.review_state = TextReview.ZAAKCEPTOWANY if accepted else TextReview.DO_KONTROLI
        if accepted:
            version.reviewed_by = ACTOR
            version.reviewed_at = now()
        else:
            version.note = "Niska ocena parsera: " + (
                "; ".join(result.issues) or f"jakość {result.quality:.2f}"
            )
        s.add(version)
        s.flush()

        units = {u.unit_key: u for u in s.scalars(select(LegalUnit).where(LegalUnit.act_id == act.id))}
        for key, parsed in result.units.items():
            unit = units.get(key)
            if unit is None:
                unit = LegalUnit(
                    act_id=act.id, unit_key=key, label=parsed.label, slug=unit_slug(act.slug, key)
                )
                s.add(unit)
                s.flush()
                units[key] = unit
            s.add(
                LegalUnitVersion(
                    unit_id=unit.id,
                    text_version_id=version.id,
                    content=parsed.content,
                    content_hash=parsed.content_hash,
                )
            )
        record(
            s,
            actor=ACTOR,
            entity="legal_text_version",
            entity_id=version.id,
            action="nowa_wersja_tekstu",
            akt=act.slug,
            zrodlo=src.eli,
            jakosc=result.quality,
            stan=version.review_state,
        )
        if not accepted:
            tasks.ensure_task(
                s,
                kind=TaskKind.KONTROLA_PARSERA,
                act_id=act.id,
                dedupe_key=f"kontrola:{act.id}:{fetched.snapshot.sha256}",
                title=f"{act.short_title}: wynik parsera {src.journal_display} wymaga kontroli",
                details={
                    "tekst": src.eli,
                    "jakosc": result.quality,
                    "uwagi": result.issues[:20],
                    "wersja_tekstu": version.id,
                },
            )
        return version

    def _diff_units(self, s: Session, act: LegalAct, old: LegalTextVersion, new: LegalTextVersion) -> int:
        def hashes(version_id: int) -> dict[int, str]:
            rows = s.execute(
                select(LegalUnitVersion.unit_id, LegalUnitVersion.content_hash).where(
                    LegalUnitVersion.text_version_id == version_id
                )
            ).all()
            return {unit_id: h for unit_id, h in rows}

        before, after = hashes(old.id), hashes(new.id)
        changed_ids = [uid for uid, h in before.items() if after.get(uid) != h]
        for unit_id in changed_ids:
            unit = s.get(LegalUnit, unit_id)
            assert unit is not None
            removed = unit_id not in after
            what = "zniknęła z nowego tekstu" if removed else "ma nowe brzmienie"
            reason = f"{act.short_title}, {unit.label} {what} ({new.journal_display}). Treść czeka na ponowne sprawdzenie."
            self._suspend_dependent(s, unit, reason)
            tasks.ensure_task(
                s,
                kind=TaskKind.ZMIANA_TEKSTU,
                act_id=act.id,
                unit_id=unit_id,
                dedupe_key=f"zmiana:{unit_id}:{new.id}",
                title=f"{act.short_title}, {unit.label}: {what}",
                details={"poprzedni_tekst": old.id, "nowy_tekst": new.id},
            )
        return len(changed_ids)

    def _suspend_dependent(self, s: Session, unit: LegalUnit, reason: str) -> None:
        """Zawiesza opublikowane objaśnienia i węzły kreatora oparte na zmienionej jednostce.

        Jednostka nadrzędna zmienia się razem z każdą podrzędną (jej treść je zawiera), więc
        wystarczy dokładne dopasowanie — objaśnienie pkt 1a nie jest zawieszane przez zmianę pkt 2.
        """
        published = s.scalars(
            select(ExplanationVersion)
            .join(Explanation, Explanation.id == ExplanationVersion.explanation_id)
            .where(Explanation.unit_id == unit.id, ExplanationVersion.state == EditorialState.OPUBLIKOWANY)
        ).all()
        for version in published:
            system_suspend(s, version, reason=reason, actor=ACTOR)

        nodes = s.scalars(
            select(DecisionTreeNodeVersion)
            .join(DecisionTreeVersion, DecisionTreeVersion.id == DecisionTreeNodeVersion.tree_version_id)
            .where(DecisionTreeVersion.state == EditorialState.OPUBLIKOWANY)
        ).all()
        for node in nodes:
            if unit.slug in (node.unit_slugs or []):
                flag_content(
                    s, entity="decision_tree_node_version", entity_id=node.id, reason=reason, actor=ACTOR
                )

    def _detect_amendments(self, s: Session, act: LegalAct, meta: ActMetadata, status_date: date) -> int:
        """Zapisuje nowelizacje z okna wokół stanu prawnego tekstu; zadanie tworzy dla tych, których tekst nie zawiera.

        Nowelizacja ogłoszona przed stanem prawnym, ale wchodząca w życie później, też nie jest w tekście —
        dlatego pobieramy metadane nowelizacji z roku poprzedzającego stan prawny, a nie tylko późniejszych.
        Czy dana nowelizacja jest „późniejsza”, liczymy przy odczycie względem bieżącego tekstu (freshness).
        """
        known = set(
            s.scalars(select(DetectedAmendment.amending_eli).where(DetectedAmendment.act_id == act.id))
        )
        window_start = status_date - timedelta(days=365)
        new_count = 0
        for ref in meta.refs("amended_by"):
            if ref.id in known or (ref.on is not None and ref.on < window_start):
                continue
            _, am = self._metadata(ref.id, kind="metadata_nowelizacja", act_id=act.id)
            published = am.promulgation or ref.on
            amendment = DetectedAmendment(
                act_id=act.id,
                amending_eli=am.eli,
                title=am.title,
                journal_display=am.journal_display,
                published_on=published,
                entry_into_force=am.entry_into_force,
            )
            s.add(amendment)
            s.flush()
            known.add(am.eli)
            record(
                s,
                actor=ACTOR,
                entity="detected_amendment",
                entity_id=amendment.id,
                action="wykryto",
                akt=act.slug,
                eli=am.eli,
            )
            if not is_later_than(
                Amendment(am.eli, am.journal_display, amendment.published_on, amendment.entry_into_force),
                status_date,
            ):
                continue
            new_count += 1
            tasks.ensure_task(
                s,
                kind=TaskKind.NOWELIZACJA,
                act_id=act.id,
                dedupe_key=f"nowelizacja:{act.id}:{am.eli}",
                title=f"{act.short_title}: nowelizacja {am.journal_display} późniejsza niż tekst ze stanem na {status_date.isoformat()}",
                details={
                    "eli": am.eli,
                    "wejscie_w_zycie": am.entry_into_force.isoformat() if am.entry_into_force else None,
                },
                due_on=am.entry_into_force,
            )
        return new_count
