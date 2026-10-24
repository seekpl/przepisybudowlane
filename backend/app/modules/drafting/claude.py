"""Szkic objaśnienia od Claude — wyjście w schemacie JSON, każde zdanie z cytatem (arkusz, działanie 3.3).

Model dostaje wyłącznie akapity przepisu z ELI (i, przy zmianie brzmienia, poprzednie objaśnienie jako
wzór układu). Klient jest wstrzykiwany: w testach zastępuje go atrapa z tą samą metodą
``beta.messages.create``. Klucz API czyta SDK ze zmiennej ``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.modules.drafting.sources import Fragment
from app.modules.drafting.validators import Quote, Sentence

# Odmowę modelu API samo ponawia na modelu zastępczym dobranym do rodzaju odmowy.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000

SYSTEM = """\
Piszesz objaśnienie przepisu prawa budowlanego dla osoby, która buduje dom i nie jest prawnikiem.

Zasady, od których nie ma wyjątków:
1. Korzystasz wyłącznie z akapitów przepisu podanych w wiadomości. Nie dodajesz wiedzy spoza nich: innych \
przepisów, orzecznictwa, praktyki urzędów, nazw organów, terminów ani kwot, których w akapitach nie ma.
2. Każde zdanie ma co najmniej jeden cytat: identyfikator akapitu (np. A2) i dosłowny fragment tego \
akapitu — kilka kolejnych słów przepisanych znak w znak, na których zdanie się opiera.
3. Liczby, daty, jednostki i odesłania (art., §, ust., pkt, lit.) przepisujesz dokładnie tak, jak stoją \
w tekście. Nie zamieniasz słów na cyfry ani odwrotnie („niewięcej niż dwukondygnacyjny” zostaje słowami).
4. Piszesz krótkimi zdaniami, w drugiej osobie („możesz”, „musisz”), bez żargonu. Dwa do czterech \
akapitów, w każdym jedno do trzech zdań.
5. Nie oceniasz konkretnych przypadków i nie obiecujesz wyniku. Nie piszesz „zawsze” ani „nigdy”, jeśli \
przepis tak nie mówi. Gdy przepis odsyła do innego przepisu, mówisz, że trzeba go sprawdzić — nie \
streszczasz go.
6. Jeśli dostajesz poprzednie objaśnienie, zachowujesz jego układ i sformułowania tam, gdzie znaczenie \
przepisu się nie zmieniło, a zmieniasz tylko to, czego dotyczy nowe brzmienie. Fakty bierzesz wyłącznie \
z nowego brzmienia.
7. Jeśli z akapitów nie da się napisać rzetelnego objaśnienia, zwracasz pustą listę akapitów i piszesz \
dlaczego w polu „uwagi”.

Pole „uwagi” jest dla recenzenta: co było niejasne, co pominąłeś i dlaczego. Może być puste.
"""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "akapity": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "zdania": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tekst": {"type": "string"},
                                "cytaty": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "akapit": {"type": "string"},
                                            "cytat": {"type": "string"},
                                        },
                                        "required": ["akapit", "cytat"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["tekst", "cytaty"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["zdania"],
                "additionalProperties": False,
            },
        },
        "uwagi": {"type": "string"},
    },
    "required": ["akapity", "uwagi"],
    "additionalProperties": False,
}


class _Quote(BaseModel):
    akapit: str
    cytat: str


class _Sentence(BaseModel):
    tekst: str
    cytaty: list[_Quote]


class _Paragraph(BaseModel):
    zdania: list[_Sentence]


class _Output(BaseModel):
    akapity: list[_Paragraph]
    uwagi: str = ""


class DraftError(Exception):
    """Szkic nie powstał (odmowa, ucięta odpowiedź, błąd API). Zadanie zostaje otwarte."""


@dataclass
class ModelDraft:
    paragraphs: list[list[Sentence]]
    notes: str
    model: str


def user_message(
    unit_label: str,
    act_title: str,
    fragments: list[Fragment],
    previous: str | None = None,
    old_fragments: list[Fragment] | None = None,
) -> str:
    def block(items: list[Fragment]) -> str:
        return "\n".join(f'<akapit id="{f.id}" przepis="{f.label}">{f.text}</akapit>' for f in items)

    parts = [
        f"Akt: {act_title}\nPrzepis do objaśnienia: {unit_label}\n\n<przepis>\n{block(fragments)}\n</przepis>"
    ]
    if old_fragments is not None:
        old = "\n".join(f'<akapit przepis="{f.label}">{f.text}</akapit>' for f in old_fragments)
        parts.append(
            f"Poprzednie brzmienie przepisu (tylko do porównania, nie cytuj go):\n<stare>\n{old}\n</stare>"
        )
    if previous:
        parts.append(
            f"Poprzednie objaśnienie (wzór układu, nie źródło faktów):\n<objasnienie>\n{previous}\n</objasnienie>"
        )
    parts.append("Napisz objaśnienie według zasad. Cytuj wyłącznie akapity z <przepis>.")
    return "\n\n".join(parts)


def draft(
    client: Any,
    *,
    model: str,
    effort: str,
    message: str,
) -> ModelDraft:
    import anthropic

    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
    except anthropic.APIConnectionError as exc:
        raise DraftError(f"Brak połączenia z Claude API: {exc}") from exc
    except anthropic.RateLimitError as exc:
        raise DraftError("Limit zapytań Claude API — spróbujemy w następnym przebiegu.") from exc
    except anthropic.APIStatusError as exc:
        raise DraftError(f"Claude API zwróciło błąd {exc.status_code}: {exc.message}") from exc

    if response.stop_reason == "refusal":
        raise DraftError("Model odmówił napisania szkicu — objaśnienie napisze redaktor.")
    if response.stop_reason == "max_tokens":
        raise DraftError("Odpowiedź modelu została ucięta (limit długości).")
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    if not texts:
        raise DraftError("Odpowiedź modelu nie zawiera tekstu.")
    try:
        out = _Output.model_validate(json.loads(texts[-1]))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise DraftError(f"Odpowiedź modelu nie pasuje do schematu: {exc}") from exc
    return ModelDraft(
        paragraphs=[
            [
                Sentence(
                    text=" ".join(z.tekst.split()),
                    quotes=[Quote(fragment_id=c.akapit.strip(), text=c.cytat) for c in z.cytaty],
                )
                for z in p.zdania
                if z.tekst.strip()
            ]
            for p in out.akapity
        ],
        notes=out.uwagi.strip(),
        model=response.model,
    )
