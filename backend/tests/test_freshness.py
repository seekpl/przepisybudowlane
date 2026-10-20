"""Testy stanu prawnego (krytyczne). Ich przypadki i oczekiwane wyniki musi zatwierdzić prawnik —
tu są propozycje zespołu, oznaczone w nazwach scenariuszy z planu."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.freshness.engine import Amendment, Confirmation, FreshnessInput, Interval, evaluate

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
TODAY = date(2026, 10, 20)
THRESHOLD = timedelta(hours=72)


def inp(**kw: object) -> FreshnessInput:
    base: dict[str, object] = {
        "now": NOW,
        "today": TODAY,
        "threshold": THRESHOLD,
        "text_type": "jednolity",
        "legal_status_date": date(2026, 3, 20),
        "sync_ok": NOW - timedelta(hours=1),
    }
    base.update(kw)
    return FreshnessInput(**base)  # type: ignore[arg-type]


def codes(f) -> list[str]:  # type: ignore[no-untyped-def]
    return [r.code for r in f.reasons]


def test_fresh_consolidated_text_is_confirmed_with_basis_and_scope() -> None:
    f = evaluate(inp())
    assert f.status == "potwierdzona"
    assert f.date == TODAY
    assert f.confirmation_scope and "ELI" in f.confirmation_scope
    assert f.notices == []


def test_without_any_confirmation_text_is_never_called_current() -> None:
    f = evaluate(inp(sync_ok=None))
    assert f.status == "niepotwierdzona"
    assert "brak_potwierdzenia" in codes(f)


def test_multi_day_sync_outage_does_not_pretend_freshness() -> None:
    f = evaluate(inp(sync_ok=NOW - timedelta(days=4)))
    assert f.status == "niepotwierdzona"
    assert "dane_nieswieze" in codes(f)


def test_sync_exactly_at_threshold_is_still_confirmed() -> None:
    assert evaluate(inp(sync_ok=NOW - THRESHOLD)).status == "potwierdzona"


def test_manual_verification_counts_when_newer_than_sync() -> None:
    f = evaluate(inp(sync_ok=None, verification=Confirmation(NOW - timedelta(hours=5), "porównanie z Dz.U.")))
    assert f.status == "potwierdzona"
    assert f.confirmation_scope == "porównanie z Dz.U."


AM = "DU/2026/900"


@pytest.mark.parametrize(
    ("entry", "expected", "code"),
    [
        (TODAY + timedelta(days=1), "zmiana", "nowelizacja_w_drodze"),  # dzień przed wejściem w życie
        (TODAY, "niepotwierdzona", "nowelizacja_obowiazuje"),  # w dniu wejścia w życie
        (TODAY - timedelta(days=1), "niepotwierdzona", "nowelizacja_obowiazuje"),  # po wejściu w życie
    ],
)
def test_amendment_around_entry_into_force(entry: date, expected: str, code: str) -> None:
    f = evaluate(inp(amendments=[Amendment(AM, "Dz.U. 2026 poz. 900", date(2026, 9, 30), entry)]))
    assert f.status == expected
    assert code in codes(f)
    if expected == "zmiana":
        assert f.effective_date == entry


def test_published_but_not_yet_binding_amendment_shows_date_and_current_text() -> None:
    f = evaluate(inp(amendments=[Amendment(AM, "Dz.U. 2026 poz. 900", date(2026, 9, 30), date(2027, 1, 1))]))
    assert f.status == "zmiana"
    assert f.effective_date == date(2027, 1, 1)
    assert "obowiązuje dziś" in f.notices[0].body


def test_amendment_already_in_consolidated_text_is_ignored() -> None:
    old = Amendment("DU/2025/100", "Dz.U. 2025 poz. 100", date(2025, 2, 1), date(2025, 3, 1))
    assert evaluate(inp(amendments=[old])).status == "potwierdzona"


def test_amendment_published_before_status_date_but_binding_later_is_not_in_text() -> None:
    am = Amendment("DU/2026/50", "Dz.U. 2026 poz. 50", date(2026, 2, 1), date(2026, 12, 1))
    f = evaluate(inp(amendments=[am]))
    assert f.status == "zmiana"


def test_amendment_incorporated_in_compilation_is_ignored() -> None:
    am = Amendment(AM, "Dz.U. 2026 poz. 900", date(2026, 9, 30), date(2026, 10, 1))
    f = evaluate(inp(text_type="kompilacja", incorporated=frozenset({AM}), amendments=[am]))
    assert f.status == "potwierdzona"


def test_amendment_without_entry_date_is_unconfirmed() -> None:
    f = evaluate(inp(amendments=[Amendment(AM, "Dz.U. 2026 poz. 900", date(2026, 9, 30), None)]))
    assert f.status == "niepotwierdzona"
    assert "nowelizacja_bez_daty" in codes(f)


def test_transitional_provision_after_loss_of_force() -> None:
    f = evaluate(
        inp(
            intervals=[
                Interval("utracil_moc", date(2026, 9, 20)),
                Interval(
                    "stosowany_przejsciowo",
                    date(2026, 9, 20),
                    title="Utraciły moc 20 września 2026 r.",
                    description="Art. 102a",
                ),
            ]
        )
    )
    assert f.status == "przejsciowa"
    assert f.date == date(2026, 9, 20)
    assert codes(f) == [
        "stosowany_przejsciowo"
    ]  # utrata mocy nie dubluje komunikatu, gdy jest przepis przejściowy


def test_transitional_period_that_ended_falls_back_to_repealed() -> None:
    f = evaluate(
        inp(
            intervals=[
                Interval("utracil_moc", date(2025, 1, 1)),
                Interval("stosowany_przejsciowo", date(2025, 1, 1), valid_to=date(2026, 6, 30)),
            ]
        )
    )
    assert f.status == "niepotwierdzona"
    assert "utracil_moc" in codes(f)


def test_repeal_announced_for_the_future_is_a_change_in_progress() -> None:
    f = evaluate(inp(intervals=[Interval("utracil_moc", date(2027, 1, 1))]))
    assert f.status == "zmiana"
    assert f.effective_date == date(2027, 1, 1)


def test_suspended_content_is_the_strongest_signal() -> None:
    f = evaluate(
        inp(
            intervals=[
                Interval("zawieszony", date(2026, 1, 1)),
                Interval("stosowany_przejsciowo", date(2026, 9, 20)),
            ],
            amendments=[Amendment(AM, "Dz.U. 2026 poz. 900", date(2026, 9, 30), date(2027, 1, 1))],
        )
    )
    assert f.status == "zawieszona"
    assert f.notices[0].status == "zawieszona"  # najpoważniejszy komunikat pierwszy


def test_unknown_text_type_is_never_current_even_when_fresh() -> None:
    f = evaluate(inp(text_type="nierozpoznany", legal_status_date=None))
    assert f.status == "niepotwierdzona"
    assert "typ_nierozpoznany" in codes(f)


def test_consolidated_text_without_status_date_cannot_be_confirmed() -> None:
    f = evaluate(inp(legal_status_date=None))
    assert f.status == "niepotwierdzona"
    assert "brak_stanu_prawnego" in codes(f)


def test_unit_missing_from_latest_text_is_flagged() -> None:
    f = evaluate(inp(unit_missing_from="Dz.U. 2027 poz. 1"))
    assert f.status == "niepotwierdzona"
    assert "jednostka_usunieta" in codes(f)


def test_no_text_at_all() -> None:
    f = evaluate(inp(text_type=None, legal_status_date=None))
    assert f.status == "niepotwierdzona"
    assert "brak_tekstu" in codes(f)
