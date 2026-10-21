from __future__ import annotations

import pytest

from app.modules.parser.units import html_to_lines, parse_units
from tests.conftest import FIXTURES


def test_fixture_text_parses_with_full_quality() -> None:
    r = parse_units((FIXTURES / "DU_2026_524.html").read_text(encoding="utf-8"))
    assert r.quality == 1.0
    assert r.issues == []
    assert {"art_28", "art_28.ust_1", "art_29.ust_1.pkt_1a", "art_29.ust_2"} <= set(r.units)


def test_point_gets_lead_in_and_article_marker_is_merged_with_first_paragraph() -> None:
    r = parse_units((FIXTURES / "DU_2026_524.html").read_text(encoding="utf-8"))
    pkt = r.units["art_29.ust_1.pkt_1a"]
    assert pkt.label == "art. 29 ust. 1 pkt 1a"
    assert pkt.content[0]["unit"] == "Art. 29. 1."
    assert pkt.content[0]["text"].startswith("Nie wymaga decyzji o pozwoleniu na budowę")
    assert pkt.content[1]["unit"] == "1a)"
    assert "70 m²" in pkt.content[1]["text"]


def test_text_is_not_modified_apart_from_whitespace() -> None:
    lines = html_to_lines("<p>Art. 1.&nbsp;Tekst   <b>po</b>grubiony\n w dwóch wierszach</p>")
    assert lines == ["Art. 1. Tekst pogrubiony w dwóch wierszach"]
    assert html_to_lines("<p>Pierwszy<br>drugi</p>") == ["Pierwszy", "drugi"]


def test_regulation_paragraphs_with_points_and_section() -> None:
    html = """<p>Na podstawie art. 7 ustawy...</p>
    <p>§ 12. 1. Budynek należy sytuować w odległości nie mniejszej niż:</p>
    <p>1) 4 m – ściana z oknami;</p><p>2) 3 m – ściana bez okien.</p>
    <p>2. Dopuszcza się sytuowanie przy granicy.</p><p>§ 13. Tekst.</p>"""
    r = parse_units(html)
    assert r.quality == 1.0
    assert [p["unit"] for p in r.units["par_12.ust_1"].content] == ["§ 12. 1.", "1)", "2)"]
    assert r.units["par_12.ust_2"].label == "§ 12 ust. 2"
    assert r.units["par_13"].content == [{"unit": "§ 13.", "text": "Tekst."}]


def test_code_style_paragraphs_inside_article() -> None:
    r = parse_units("<p>Art. 10. § 1. Organy zapewniają stronom udział.</p><p>§ 2. Wyjątek.</p>")
    assert r.units["art_10.par_1"].label == "art. 10 § 1"
    assert r.units["art_10.par_2"].content == [{"unit": "§ 2.", "text": "Wyjątek."}]


def test_chapter_titles_do_not_leak_into_previous_article() -> None:
    r = parse_units("<p>Art. 1. Tekst.</p><p>Rozdział 2</p><p>Utrzymanie obiektów</p><p>Art. 2. Drugi.</p>")
    assert r.units["art_1"].content == [{"unit": "Art. 1.", "text": "Tekst."}]


def test_common_part_after_enumeration_belongs_to_the_section_not_the_last_point() -> None:
    r = parse_units(
        "<p>Art. 5. 1. Wprowadzenie:</p><p>1) pierwszy,</p><p>2) drugi</p><p>– jeżeli spełnia warunki.</p>"
        "<p>zdanie wspólne.</p>"
    )
    assert r.units["art_5.ust_1.pkt_2"].content[-1]["text"] == "– jeżeli spełnia warunki."
    assert r.units["art_5.ust_1"].content[-1]["text"] == "zdanie wspólne."
    assert all(p["text"] != "zdanie wspólne." for p in r.units["art_5.ust_1.pkt_2"].content)


def test_numbering_going_back_lowers_quality() -> None:
    r = parse_units("<p>Art. 5. Tekst.</p><p>Art. 3. Cofnięta numeracja.</p>")
    assert r.quality < 1.0
    assert any("cofa" in i for i in r.issues)


def test_document_without_units_has_zero_quality() -> None:
    r = parse_units("<p>Skan bez warstwy tekstowej</p>")
    assert r.quality == 0.0
    assert r.units == {}


def test_content_hash_is_stable_and_sensitive() -> None:
    a = parse_units("<p>Art. 1. Tekst.</p>").units["art_1"]
    b = parse_units("<p>Art. 1.   Tekst.</p>").units["art_1"]
    c = parse_units("<p>Art. 1. Tekst zmieniony.</p>").units["art_1"]
    assert a.content_hash == b.content_hash != c.content_hash


# --- struktura ELI (HTML z api.sejm.gov.pl) --------------------------------------------------------

ELI_HTML = """<html><body>
<h1><span class="head-type">Obwieszczenie Ministra</span></h1>
<section id="part_1"><div class="unit unit_pass" data-id="pass_1" id="pass_1"><h3>1.</h3>
  <div class="unit-inner"><div class="pro-text" data-template="xText">Ogłasza się tekst jednolity.</div></div></div>
</section>
<section id="part_2"><div class="part"><h2 class="part">Załącznik - Tekst jednolity rozporządzenia</h2>
 <div class="unit unit_bran" data-id="bran_II" id="bran_II"><div class="unit-inner">
  <div class="unit unit_para" data-id="para_12" id="bran_II-para_12"><h3><b>§&nbsp;12.</b></h3><div class="unit-inner">
   <div class="unit unit_pass" data-id="pass_1" id="bran_II-para_12-pass_1"><h3>1.</h3><div class="unit-inner">
     <div class="pro-text" data-template="xText">Budynek należy sytuować<a class="gloss-link tooltip" href="#g"><sup>3)</sup>
       <span class="tooltip-text">Przypis o zmianie § 12.</span></a> w odległości nie mniejszej niż:</div>
     <div class="unit unit_pint" data-id="pint_1" id="p1"><h3>1)</h3><div class="unit-inner">
       <div class="pro-text" data-template="xText">4 m – ze ścianą z oknami,</div></div></div>
     <div class="unit unit_pint" data-id="pint_2" id="p2"><h3>2)</h3><div class="unit-inner">
       <div class="pro-text" data-template="xText">3 m – ze ścianą bez okien</div></div></div>
     <div class="pro-text" data-template="xText">– od granicy działki o powierzchni 20 m<sup>2</sup>.</div>
   </div></div>
   <div class="unit unit_pass" data-id="pass_2" id="bran_II-para_12-pass_2"><h3>2 <a class="gloss-link"><sup>4)</sup></a> .</h3>
     <div class="unit-inner"><div class="pro-text" data-template="xText">(uchylony)</div></div></div>
  </div></div>
 </div></div>
</div></section>
<section id="part_3"><h2>Załącznik nr 1 - Wykaz norm</h2>
 <div class="unit unit_para" data-id="para_1" id="z-para_1"><h3>§ 1.</h3><div class="unit-inner">
   <div class="pro-text" data-template="xText">Nie należy do tekstu jednolitego.</div></div></div>
</section>
</body></html>"""


def test_eli_structure_takes_consolidated_text_from_annex_without_footnotes() -> None:
    r = parse_units(ELI_HTML)
    assert r.quality == 1.0, r.issues
    assert set(r.units) == {
        "par_12",
        "par_12.ust_1",
        "par_12.ust_1.pkt_1",
        "par_12.ust_1.pkt_2",
        "par_12.ust_2",
    }
    ust = r.units["par_12.ust_1"].content
    assert ust[0] == {"unit": "§ 12. 1.", "text": "Budynek należy sytuować w odległości nie mniejszej niż:"}
    # Część wspólna po wyliczeniu należy do ustępu, nie do ostatniego punktu.
    assert ust[-1] == {"unit": "", "text": "– od granicy działki o powierzchni 20 m²."}
    assert r.units["par_12.ust_1.pkt_2"].content == [
        ust[0],
        {"unit": "2)", "text": "3 m – ze ścianą bez okien"},
    ]
    # Odsyłacz do przypisu w oznaczeniu jednostki znika razem z przypisem.
    assert r.units["par_12.ust_2"].content == [{"unit": "2.", "text": "(uchylony)"}]


def test_eli_structure_flags_units_out_of_place() -> None:
    html = ELI_HTML.replace('data-id="pint_2"', 'data-id="none_2"')
    r = parse_units(html)
    assert r.quality < 1.0
    assert any("bez rozpoznanego rodzaju" in i for i in r.issues)


# --- nagrania z prawdziwego ELI ----------------------------------------------------------------------

RECORDED = FIXTURES / "recorded" / "acts" / "DU"
WT_TJ = RECORDED / "2022" / "1225" / "text.html"
PB_TJ = RECORDED / "2026" / "524" / "text.pdf"


@pytest.mark.skipif(not WT_TJ.exists(), reason="brak nagrania t.j. warunków technicznych")
def test_real_eli_html_consolidated_text() -> None:
    from app.config import get_settings

    r = parse_units(WT_TJ.read_text(encoding="utf-8"))
    assert r.quality >= get_settings().parser_quality_threshold, r.issues[:10]
    par = r.units["par_12.ust_1"].content
    assert par[0]["unit"] == "§ 12. 1."
    assert par[0]["text"].startswith("Jeżeli z przepisów § 13, 19, 23, 36, 40, 60 i 271-273")
    assert par[1:] == [
        {
            "unit": "1)",
            "text": "4 m - w przypadku budynku zwróconego ścianą z oknami lub drzwiami w stronę tej granicy;",
        },
        {
            "unit": "2)",
            "text": "3 m - w przypadku budynku zwróconego ścianą bez okien i drzwi w stronę tej granicy.",
        },
    ]
    # Treść obwieszczenia i przypisy nie trafiają do jednostek tekstu jednolitego.
    assert not any("Ogłasza się" in p["text"] for u in r.units.values() for p in u.content)


@pytest.fixture(scope="module")
def pb_pdf():  # type: ignore[no-untyped-def]
    from app.modules.parser.pdf import parse_pdf

    return parse_pdf(PB_TJ.read_bytes())


@pytest.mark.skipif(not PB_TJ.exists(), reason="brak nagrania t.j. Prawa budowlanego")
def test_real_pdf_consolidated_text(pb_pdf) -> None:  # type: ignore[no-untyped-def]
    r = pb_pdf
    assert next(iter(r.units)) == "art_1" and "art_108" in r.units
    assert r.units["art_28.ust_1"].content == [
        {
            "unit": "Art. 28. 1.",
            "text": "Roboty budowlane można rozpocząć jedynie na podstawie decyzji o pozwoleniu na budowę, "
            "z zastrzeżeniem art. 29–31.",
        }
    ]
    pkt = r.units["art_29.ust_1.pkt_1a"].content
    assert pkt[1]["unit"] == "1a)"
    assert "o powierzchni zabudowy do 70 m², których obszar oddziaływania" in pkt[1]["text"]
    # Odsyłacz do przypisu („1b)¹⁵⁾”) nie zostaje w oznaczeniu ani w tekście.
    assert r.units["art_29.ust_1.pkt_1b"].content[1]["unit"] == "1b)"
    # Tekst obwieszczenia (przepisy przejściowe nowelizacji) nie trafia do jednostek ustawy.
    assert not any("Marszałek Sejmu" in p["text"] for u in r.units.values() for p in u.content)
