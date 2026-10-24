"""Zapytania bez wyników → propozycje synonimów (arkusz, działanie 5.4).

Zapisujemy wyłącznie znormalizowane zapytanie i licznik. Propozycja to słowa z indeksu najbardziej
podobne do nieznanego słowa (literówka, potoczna forma) — redakcja jednym kliknięciem dodaje synonim
do jawnego słownika albo odrzuca propozycję.
"""

from __future__ import annotations

import difflib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import today
from app.models import SearchDocument, SearchMiss, SearchSynonym
from app.modules.search.stemmer import fold, tokens

MAX_LEN = 80
MAX_WORDS = 5
# Adres e-mail, ciąg cyfr (PESEL, telefon, numer działki z obrębem) albo coś, co wygląda na adres.
_PERSONAL = re.compile(r"@|\d{4,}|\b(ul|al|os)\.?\s+\w+\s+\d", re.IGNORECASE)


def normalize(q: str) -> str | None:
    """Zapytanie do zapisu albo None, gdy może zawierać dane osobowe lub jest za długie."""
    text = " ".join(q.lower().split())
    if not text or len(text) > MAX_LEN or len(text.split()) > MAX_WORDS or _PERSONAL.search(text):
        return None
    return text


def record_miss(s: Session, q: str) -> None:
    text = normalize(q)
    if text is None:
        return
    miss = s.scalar(select(SearchMiss).where(SearchMiss.query == text))
    if miss is None:
        s.add(SearchMiss(query=text, count=1, first_seen_on=today(), last_seen_on=today()))
    else:
        miss.count += 1
        miss.last_seen_on = today()


def proposals(s: Session, limit: int = 30) -> list[dict[str, object]]:
    """Najczęstsze nierozwiązane zapytania z podpowiedzią słów z indeksu, które mogły być szukane."""
    vocabulary: dict[str, str] = {}
    for title, body in s.execute(select(SearchDocument.title, SearchDocument.body)):
        for word in re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{4,}", f"{title} {body}"):
            vocabulary.setdefault(fold(word), word.lower())
    known = {fold(x) for x in s.scalars(select(SearchSynonym.term))}
    out = []
    for miss in s.scalars(
        select(SearchMiss)
        .where(SearchMiss.resolved.is_(None))
        .order_by(SearchMiss.count.desc(), SearchMiss.last_seen_on.desc())
        .limit(limit)
    ):
        if fold(miss.query) in known:
            continue
        suggestions: list[str] = []
        for token in tokens(miss.query):
            for match in difflib.get_close_matches(token, vocabulary.keys(), n=3, cutoff=0.75):
                if vocabulary[match] not in suggestions:
                    suggestions.append(vocabulary[match])
        out.append({"id": miss.id, "zapytanie": miss.query, "liczba": miss.count, "propozycje": suggestions})
    return out
