"""Klient ELI API: JSON i teksty aktów, bez „scrapowania” stron.

Ponawia żądania przy przekroczeniu czasu, błędach sieci, 5xx i 429 (z narastającym odstępem).
404 i inne 4xx nie są ponawiane. Każda odpowiedź wraca z czasem trwania — trafia do ``source_fetch``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

USER_AGENT = "przepisy-budowlane/0.1 (+synchronizacja ELI; kontakt: redakcja)"


class EliError(Exception):
    def __init__(self, message: str, *, url: str, status: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status = status


class EliNotFound(EliError):
    pass


class EliUnavailable(EliError):
    pass


@dataclass(frozen=True)
class EliResponse:
    url: str
    status: int
    content: bytes
    content_type: str | None
    duration_ms: int


def act_path(eli: str) -> str:
    publisher, year, pos = eli.split("/")
    return f"/acts/{publisher}/{year}/{pos}"


class EliClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff = backoff
        self._sleep = sleep
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html, application/pdf"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get(self, path: str, params: dict[str, str] | None = None) -> EliResponse:
        url = self.url(path)
        last_error: str = "nieznany błąd"
        last_status: int | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                resp = self._http.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                last_status = None
            else:
                duration = int((time.monotonic() - started) * 1000)
                if resp.status_code == 404:
                    raise EliNotFound("Nie znaleziono zasobu w ELI", url=url, status=404)
                if resp.status_code < 400:
                    return EliResponse(
                        url=str(resp.request.url),
                        status=resp.status_code,
                        content=resp.content,
                        content_type=resp.headers.get("content-type"),
                        duration_ms=duration,
                    )
                last_status = resp.status_code
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code < 500 and resp.status_code != 429:
                    raise EliError(f"ELI odrzuciło żądanie: {last_error}", url=url, status=resp.status_code)
            if attempt < self.max_retries:
                self._sleep(self.backoff * (2**attempt))
        raise EliUnavailable(
            f"ELI niedostępne po {self.max_retries + 1} próbach: {last_error}", url=url, status=last_status
        )
