"""Parser jednostek redakcyjnych: HTML tekstu aktu → artykuły/paragrafy, ustępy, punkty, litery.

Działa na tekście bloków, a nie na znacznikach konkretnego wydawcy — zmiana układu HTML w ELI
nie psuje go po cichu, tylko obniża ocenę jakości. Wynik poniżej progu trafia do kontroli człowieka.

Tekst przepisu przenosimy bez zmian: normalizujemy wyłącznie białe znaki.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment, Declaration, Doctype, NavigableString, ProcessingInstruction, Tag

from app.modules.registry.units import unit_label

PARSER_VERSION = "units-1.0"

_BLOCK_TAGS = {
    "p",
    "div",
    "li",
    "ul",
    "ol",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "td",
    "th",
    "tr",
    "table",
    "dd",
    "dt",
    "dl",
    "blockquote",
    "pre",
    "section",
    "article",
    "header",
    "footer",
    "main",
    "body",
    "html",
}

_RE_ART = re.compile(r"^Art\.\s*(\d+[a-z]*)\.\s*(.*)$")
_RE_PAR = re.compile(r"^§\s*(\d+[a-z]*)\.\s*(.*)$")
_RE_UST = re.compile(r"^(\d+[a-z]*)\.\s+(.*)$")
_RE_PKT = re.compile(r"^(\d+[a-z]*)\)\s*(.*)$")
_RE_LIT = re.compile(r"^([a-z]{1,2})\)\s*(.*)$")
_RE_HEADING = re.compile(
    r"^(DZIAŁ|Dział|ROZDZIAŁ|Rozdział|Oddział|ODDZIAŁ|TYTUŁ|Tytuł)\s+[0-9IVXLC]+[a-z]*\b"
)
_WS = re.compile(r"\s+")


@dataclass
class Paragraph:
    unit: str
    text: str

    def as_dict(self) -> dict[str, str]:
        return {"unit": self.unit, "text": self.text}


@dataclass
class ParsedUnit:
    key: str
    label: str
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def content(self) -> list[dict[str, str]]:
        return [p.as_dict() for p in self.paragraphs]

    @property
    def content_hash(self) -> str:
        return content_hash(self.content)


@dataclass
class ParseResult:
    units: dict[str, ParsedUnit]
    quality: float
    issues: list[str]
    parser_version: str = PARSER_VERSION


def content_hash(content: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def html_to_lines(html: str) -> list[str]:
    """Wiersze tekstu w kolejności dokumentu: każdy element blokowy zaczyna nowy wiersz."""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style", "head", "template"]):
        el.decompose()
    # „m<sup>2</sup>” → „m²”: jednostki zostają czytelne, tekst się nie zmienia.
    for sup in soup.find_all("sup"):
        sup.replace_with(sup.get_text().translate(_SUPERSCRIPT))

    lines: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        text = "".join(buf)
        buf.clear()
        for raw in text.split("\n"):
            line = _WS.sub(" ", raw.replace("\u00a0", " ")).strip()
            if line:
                lines.append(line)

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                if not isinstance(child, (Comment, Doctype, Declaration, ProcessingInstruction)):
                    # Znak nowego wiersza w źródle HTML to zwykła spacja; wiersz łamie tylko <br> albo blok.
                    buf.append(str(child).replace("\n", " "))
            elif isinstance(child, Tag):
                if child.name == "br":
                    buf.append("\n")
                elif child.name in _BLOCK_TAGS:
                    flush()
                    walk(child)
                    flush()
                else:
                    # Elementy liniowe (<span>, <b>) sklejamy tak, jak wyświetla je przeglądarka.
                    walk(child)

    walk(soup)
    flush()
    return lines


class _Builder:
    def __init__(self) -> None:
        self.units: dict[str, ParsedUnit] = {}
        self.issues: list[str] = []
        self.top_kind: str | None = None  # "art" | "par"
        self.top: str | None = None
        self.mid: str | None = None  # ustęp albo § wewnątrz artykułu
        self.mid_kind: str | None = None
        self.pkt: str | None = None
        self.lit: str | None = None
        self.lead_in: dict[str, Paragraph] = {}
        self.last: Paragraph | None = None
        # „Art. 29.” w osobnym wierszu łączymy z oznaczeniem pierwszego ustępu: „Art. 29. 1.”.
        self.pending: str | None = None

    # --- klucze i etykiety
    def _keys(self) -> list[str]:
        keys: list[str] = []
        if self.top is None:
            return keys
        k = f"{self.top_kind}_{self.top}"
        keys.append(k)
        if self.mid is not None:
            k += f".{self.mid_kind}_{self.mid}"
            keys.append(k)
        if self.pkt is not None:
            k += f".pkt_{self.pkt}"
            keys.append(k)
        if self.lit is not None:
            k += f".lit_{self.lit}"
            keys.append(k)
        return keys

    def _label(self, key: str) -> str:
        return unit_label(key)

    def _emit(self, para: Paragraph) -> None:
        keys = self._keys()
        for key in keys:
            unit = self.units.get(key)
            if unit is None:
                unit = ParsedUnit(key=key, label=self._label(key))
                # Punkt i litera dostają wprowadzenie wyliczenia jednostki nadrzędnej — bez niego nie da się go czytać.
                parent = key.rsplit(".", 1)[0] if "." in key else None
                if parent and parent in self.lead_in and key.rsplit(".", 1)[1].startswith(("pkt_", "lit_")):
                    unit.paragraphs.append(self.lead_in[parent])
                self.units[key] = unit
            unit.paragraphs.append(para)
        if keys:
            self.lead_in.setdefault(keys[-1], para)
        self.last = para

    # --- przejścia
    def _flush_pending(self) -> None:
        if self.pending is not None:
            prefix, self.pending = self.pending, None
            self._emit(Paragraph(prefix, ""))

    def start_top(self, kind: str, num: str, display: str, rest: str) -> None:
        self._flush_pending()
        key = f"{kind}_{num}"
        if key in self.units:
            self.issues.append(f"Powtórzona jednostka: {self._label(key)}")
        self.top_kind, self.top = kind, num
        self.mid = self.mid_kind = self.pkt = self.lit = None
        prefix = display
        m_par = _RE_PAR.match(rest) if kind == "art" else None
        m_ust = _RE_UST.match(rest)
        if m_par:
            self.mid_kind, self.mid = "par", m_par.group(1)
            prefix += f" § {m_par.group(1)}."
            rest = m_par.group(2)
        elif m_ust:
            self.mid_kind, self.mid = "ust", m_ust.group(1)
            prefix += f" {m_ust.group(1)}."
            rest = m_ust.group(2)
        if not rest and self.mid is None:
            self.pending = prefix
            return
        self._emit(Paragraph(prefix, rest))

    def start_mid(self, kind: str, num: str, rest: str) -> None:
        self.mid_kind, self.mid = kind, num
        self.pkt = self.lit = None
        own = f"§ {num}." if kind == "par" else f"{num}."
        prefix = f"{self.pending} {own}" if self.pending else own
        self.pending = None
        self._emit(Paragraph(prefix, rest))

    def start_pkt(self, num: str, rest: str) -> None:
        self._flush_pending()
        self.pkt, self.lit = num, None
        self._emit(Paragraph(f"{num})", rest))

    def start_lit(self, letter: str, rest: str) -> None:
        self.lit = letter
        self._emit(Paragraph(f"{letter})", rest))

    def continuation(self, text: str) -> bool:
        if self.top is None:
            return False
        # Tiret zostaje w bieżącej jednostce; inny tekst bez oznaczenia po wyliczeniu
        # to część wspólna — należy do ustępu, nie do ostatniego punktu.
        if self.pending is not None:
            prefix, self.pending = self.pending, None
            self._emit(Paragraph(prefix, text))
            return True
        if not text.startswith(("– ", "- ")):
            self.pkt = self.lit = None
        self._emit(Paragraph("", text))
        return True


def parse_units(html: str) -> ParseResult:
    lines = html_to_lines(html)
    b = _Builder()
    started = False
    counted = 0
    assigned = 0
    last_top_num: int | None = None
    in_heading = False
    for line in lines:
        if _RE_HEADING.match(line):
            # Tytuł rozdziału stoi w kolejnych wierszach aż do pierwszej jednostki — nie należy do przepisu.
            in_heading = True
            continue
        m_art = _RE_ART.match(line)
        m_par = _RE_PAR.match(line)
        starts_top = bool(m_art or (m_par and b.top_kind in (None, "par")))
        if in_heading and not starts_top:
            continue
        in_heading = False
        if starts_top:
            started = True
            kind, m = ("art", m_art) if m_art else ("par", m_par)
            assert m is not None
            num = m.group(1)
            n = _leading_int(num)
            if last_top_num is not None and n is not None and n < last_top_num:
                b.issues.append(f"Numeracja się cofa przy {b._label(f'{kind}_{num}')}")
            last_top_num = n if n is not None else last_top_num
            b.start_top(kind, num, f"Art. {num}." if kind == "art" else f"§ {num}.", m.group(2))
        elif not started:
            continue
        elif m_par and b.top_kind == "art":
            b.start_mid("par", m_par.group(1), m_par.group(2))
        elif (m := _RE_PKT.match(line)) and b.top is not None:
            b.start_pkt(m.group(1), m.group(2))
        elif (m := _RE_LIT.match(line)) and b.pkt is not None:
            b.start_lit(m.group(1), m.group(2))
        elif ((m := _RE_UST.match(line)) and b.top_kind == "art" and b.mid_kind != "par") or (
            (m := _RE_UST.match(line)) and b.top_kind == "par"
        ):
            b.start_mid("ust", m.group(1), m.group(2))
        else:
            if b.continuation(line):
                assigned += 1
            counted += 1
            continue
        counted += 1
        assigned += 1

    b._flush_pending()
    if not started:
        return ParseResult(units={}, quality=0.0, issues=["Nie znaleziono żadnego artykułu ani paragrafu"])
    ratio = assigned / counted if counted else 0.0
    quality = max(0.0, min(1.0, ratio - 0.05 * len(b.issues)))
    return ParseResult(units=b.units, quality=round(quality, 4), issues=b.issues)


def _leading_int(num: str) -> int | None:
    m = re.match(r"\d+", num)
    return int(m.group(0)) if m else None
