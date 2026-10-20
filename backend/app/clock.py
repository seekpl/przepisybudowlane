"""Jedno źródło „teraz” — testy stanu prawnego podstawiają własny zegar."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")

_now: Callable[[], datetime] = lambda: datetime.now(UTC)  # noqa: E731


def now() -> datetime:
    return _now()


def today() -> date:
    """Dzień w Polsce — od niego zależy, czy przepis już obowiązuje."""
    return now().astimezone(WARSAW).date()


def set_clock(fn: Callable[[], datetime]) -> None:
    global _now
    _now = fn


def reset_clock() -> None:
    set_clock(lambda: datetime.now(UTC))
