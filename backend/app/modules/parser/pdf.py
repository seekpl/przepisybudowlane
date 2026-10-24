"""Tekst aktu z PDF Dziennika Ustaw → wiersze dla parsera jednostek.

Aktualne teksty jednolite wielu ustaw (np. Prawa budowlanego) ELI udostępnia tylko w PDF. Wynik z PDF
zawsze idzie do kontroli człowieka przed publikacją (arkusz, działanie 1.6) — ten moduł ma tylko oddać
tekst tak wiernie, jak pozwala układ strony:

- pomija nagłówek strony („Dziennik Ustaw – 5 – Poz. 524”), przypisy (mniejsza czcionka) i treść
  obwieszczenia przed załącznikiem z tekstem jednolitym; kończy na załącznikach do aktu;
- usuwa odsyłacze do przypisów („1b)¹⁵⁾” → „1b)”), a cyfry w indeksie górnym zamienia na „²”, „³”;
- odtwarza spacje z odstępów między znakami (PDF ich nie zawiera) i skleja wiersze w akapity;
  przeniesienie wyrazu („zastrzeże-/niem”) łączy, chyba że ten sam wyraz z łącznikiem występuje
  w dokumencie („architektoniczno-budowlanej”).
"""

from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.modules.parser.units import ParseResult, parse_lines

_HEADER = re.compile(r"^Dziennik Ustaw\s*[–-]\s*\d+\s*[–-]\s*Poz\.\s*\d+")
_ANNEX_START = re.compile(r"^Załącznik do obwieszczenia")
_ACT_ANNEX = re.compile(r"^(Załącznik|ZAŁĄCZNIK)(\s+nr\s+\d+)?\b")
_FOOTNOTE_REF = re.compile(r"^\d+\)$")
_MARKER = re.compile(
    r"^(Art\.\s*\d+[a-z]*\.|§\s*\d+[a-z]*\.|\d+[a-z]*\.\s|\d+[a-z]*\)\s|[a-z]{1,2}\)\s|[–-]\s)"
)
_HYPHENATED = re.compile(r"(\w+)-$")
_WORD_WITH_HYPHEN = re.compile(r"\b\w+-\w+\b")
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
# Odstęp (ułamek wielkości czcionki), od którego zaczyna się nowy wyraz. W wierszach ściśniętych przy
# justowaniu odstęp między wyrazami spada do ~0,14 em, a litery w wyrazie dzieli najwyżej ~0,02 em.
WORD_GAP = 0.08


@dataclass
class _Line:
    text: str
    x0: float
    centered: bool
    bold_start: bool


def _body_size(pages: list[Any]) -> float:
    sizes: Counter[float] = Counter()
    for page in pages[:30]:
        for c in page.chars:
            sizes[round(c["size"] * 2) / 2] += 1
    return sizes.most_common(1)[0][0] if sizes else 10.0


def _line_text(chars: list[dict[str, Any]], body: float) -> str:
    """Tekst wiersza ze znaków: spacje z odstępów, bez odsyłaczy do przypisów, indeks górny jako ²."""
    small = body * 0.8
    out: list[str] = []
    prev_x1: float | None = None
    i = 0
    while i < len(chars):
        c = chars[i]
        if c["size"] < small:
            j = i
            while j < len(chars) and chars[j]["size"] < small:
                j += 1
            group = "".join(ch["text"] for ch in chars[i:j])
            if not _FOOTNOTE_REF.match(group):
                if prev_x1 is not None and c["x0"] - prev_x1 > body * WORD_GAP:
                    out.append(" ")
                out.append(group.translate(_SUPERSCRIPT) if group.isdigit() else group)
            prev_x1 = chars[j - 1]["x1"]
            i = j
            continue
        if c["text"] == " " or (prev_x1 is not None and c["x0"] - prev_x1 > body * WORD_GAP):
            out.append(" ")
        out.append(c["text"])
        prev_x1 = c["x1"]
        i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _page_lines(page: Any, body: float) -> list[tuple[_Line, float]]:
    rows: list[tuple[_Line, float]] = []
    for raw in page.extract_text_lines(return_chars=True, x_tolerance=1):
        chars = [c for c in raw["chars"] if c["text"].strip() or c["text"] == " "]
        if not chars:
            continue
        size = Counter(round(c["size"] * 2) / 2 for c in chars).most_common(1)[0][0]
        text = _line_text(chars, body)
        if not text:
            continue
        x0 = raw["x0"]
        centered = x0 > page.width * 0.25 and raw["x1"] < page.width * 0.85
        bold_start = all("Bold" in c["fontname"] for c in chars[: min(4, len(chars))])
        rows.append((_Line(text, x0, centered, bold_start), size))
    return rows


def pdf_lines(content: bytes) -> list[str]:
    """Akapity tekstu aktu w kolejności dokumentu (wejście dla ``parse_lines``)."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages = list(pdf.pages)
        body = _body_size(pages)
        first_lines = (pages[0].extract_text() or "").splitlines()[:12] if pages else []
        # Obwieszczenie o tekście jednolitym: tekst aktu zaczyna się dopiero w załączniku.
        in_text = not any(line.strip().upper() == "OBWIESZCZENIE" for line in first_lines)
        lines: list[_Line] = []
        for page in pages:
            for line, size in _page_lines(page, body):
                if _HEADER.match(line.text):
                    continue
                if not in_text:
                    in_text = bool(_ANNEX_START.match(line.text))
                    continue
                if _ACT_ANNEX.match(line.text) and line.x0 > page.width * 0.25 and lines:
                    return _paragraphs(
                        lines
                    )  # załączniki do aktu (tabele, wzory) to nie jednostki redakcyjne
                if size < body - 0.5:
                    continue  # przypisy, metryka załącznika
                lines.append(line)
    return _paragraphs(lines)


def _paragraphs(lines: list[_Line]) -> list[str]:
    hyphen_words = {w.lower() for line in lines for w in _WORD_WITH_HYPHEN.findall(line.text)}
    out: list[str] = []
    prev: _Line | None = None
    for line in lines:
        starts_new = (
            prev is None
            or line.centered
            or prev.centered
            or (line.bold_start and line.text.startswith(("Art.", "§")))
            or (bool(_MARKER.match(line.text)) and out[-1].rstrip()[-1:] in (";", ":", ".", ",", "”"))
        )
        if starts_new:
            out.append(line.text)
        else:
            m = _HYPHENATED.search(out[-1])
            if m and line.text[:1].islower():
                joined = f"{m.group(1)}-{line.text.split(' ', 1)[0]}".rstrip(",.;:").lower()
                if joined in hyphen_words:
                    out[-1] = out[-1] + line.text
                else:
                    out[-1] = out[-1][:-1] + line.text
            else:
                out[-1] = f"{out[-1]} {line.text}"
        prev = line
    return out


def parse_pdf(content: bytes) -> ParseResult:
    result = parse_lines(pdf_lines(content))
    result.issues.insert(0, "Tekst z PDF — układ odczytany z położenia znaków na stronie")
    return result
