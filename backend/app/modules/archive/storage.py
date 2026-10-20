"""Archiwum źródeł: surowe odpowiedzi (JSON, HTML, PDF) adresowane sumą SHA-256.

Plik zapisujemy raz; ten sam bajt-w-bajt dokument nie zajmuje miejsca drugi raz.
W produkcji katalog wskazuje na wolumen lub magazyn obiektowy w UE.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Archive:
    def __init__(self, root: Path) -> None:
        self.root = root

    def key_for(self, digest: str) -> str:
        return f"{digest[:2]}/{digest[2:4]}/{digest}"

    def put(self, data: bytes) -> tuple[str, str]:
        """Zapisuje treść i zwraca (sha256, klucz). Zapis atomowy: najpierw plik tymczasowy, potem rename."""
        digest = sha256(data)
        key = self.key_for(digest)
        path = self.root / key
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        return digest, key

    def get(self, key: str) -> bytes:
        data = (self.root / key).read_bytes()
        if sha256(data) != Path(key).name:
            raise ValueError(f"Suma kontrolna pliku w archiwum się nie zgadza: {key}")
        return data
