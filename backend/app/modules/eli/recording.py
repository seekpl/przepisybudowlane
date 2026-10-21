"""Nagrywanie i odtwarzanie odpowiedzi ELI.

Nagrywa ten sam kod synchronizacji, który działa na produkcji (transport HTTP owinięty zapisem),
więc nagranie zawiera dokładnie to, czego synchronizacja potrzebuje — ani mniej, ani więcej.
Odtwarzanie podaje zapisane pliki zamiast sieci: testy kontraktu, środowisko deweloperskie i E2E.

Układ katalogu: ścieżka zasobu względem bazowego adresu ELI, np. ``acts/DU/1994/414.json``
i ``acts/DU/2026/524/text.html``, plus ``index.json`` z metryką każdego pliku.
Odpowiedzi z parametrami (lista zmian) nie są nagrywane — zależą od chwili wywołania.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import httpx

INDEX = "index.json"


def relative_file(base_path: str, request_path: str) -> str | None:
    """``/eli/acts/DU/1994/414`` → ``acts/DU/1994/414.json``; poza bazą ELI → None."""
    base = base_path.rstrip("/")
    if not request_path.startswith(base + "/"):
        return None
    rel = request_path[len(base) + 1 :].strip("/")
    if not rel or ".." in PurePosixPath(rel).parts:
        return None
    if not PurePosixPath(rel).suffix:
        rel += ".json"
    return rel


# 404 to też odpowiedź źródła (nie ma takiego zasobu); 403, 429 i 5xx są chwilowe i nie trafiają do nagrania.
RECORDED_STATUSES = (200, 404)


class RecordingTransport(httpx.BaseTransport):
    """Przepuszcza żądania do ``inner`` i zbiera odpowiedzi; na dysk trafiają dopiero w ``save``."""

    def __init__(self, inner: httpx.BaseTransport, out_dir: Path, base_path: str) -> None:
        self.inner = inner
        self.out_dir = out_dir
        self.base_path = base_path
        # Poprzednie nagranie: data zapisu zmienia się tylko wtedy, gdy zmieniła się treść odpowiedzi,
        # żeby codzienne nagranie bez zmian w ELI nie dawało różnic w repozytorium.
        self.previous: dict[str, dict[str, object]] = {}
        index_file = out_dir / INDEX
        if index_file.exists():
            self.previous = json.loads(index_file.read_text(encoding="utf-8"))
        self.index: dict[str, dict[str, object]] = dict(self.previous)
        self.pending: dict[str, tuple[dict[str, object], bytes]] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        rel = relative_file(self.base_path, request.url.path)
        if rel is None or request.url.query:
            return response
        content = response.read()
        if response.status_code in RECORDED_STATUSES:
            entry: dict[str, object] = {
                "url": str(request.url),
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "sha256": hashlib.sha256(content).hexdigest() if response.status_code == 200 else None,
            }
            self.pending[rel] = (entry, content)
        return httpx.Response(
            response.status_code, headers=response.headers, content=content, request=request
        )

    def save(self, *, prune: bool = False) -> None:
        """Zapisuje zebrane odpowiedzi i indeks.

        ``prune`` usuwa pliki, których ten przebieg nie pobrał (np. poprzedni tekst jednolity) — tylko po
        w pełni udanym przebiegu na świeżej bazie; inaczej wyrzuciłby teksty, których akurat nie pobrano.
        """
        index = {} if prune else dict(self.previous)
        if prune:
            for rel in set(self.previous) - set(self.pending):
                (self.out_dir / rel).unlink(missing_ok=True)
        for rel, (entry, content) in self.pending.items():
            before = self.previous.get(rel, {})
            unchanged = "recorded_at" in before and all(before.get(k) == v for k, v in entry.items())
            stamp = (
                before["recorded_at"] if unchanged else datetime.now(UTC).replace(microsecond=0).isoformat()
            )
            index[rel] = {**entry, "recorded_at": stamp}
            target = self.out_dir / rel
            if entry["status"] == 200:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            else:
                target.unlink(missing_ok=True)
        self.index = dict(sorted(index.items()))
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / INDEX).write_text(
            json.dumps(self.index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )


class ReplayTransport(httpx.BaseTransport):
    """Podaje nagrane pliki. Czego nie nagrano — 404, tak jak nieistniejący zasób w ELI."""

    def __init__(self, directory: Path, base_path: str) -> None:
        self.directory = directory
        self.base_path = base_path

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        rel = relative_file(self.base_path, request.url.path)
        if request.url.query and rel and rel.startswith("changes/"):
            # Lista zmian nie jest nagrywana: odtworzenie odświeża wszystko, jak przy jej awarii.
            return httpx.Response(200, json=[], request=request)
        path = self.directory / rel if rel else None
        if path is None or not path.is_file():
            return httpx.Response(404, json={"error": "nie nagrano"}, request=request)
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        return httpx.Response(
            200, content=path.read_bytes(), headers={"content-type": ctype}, request=request
        )
