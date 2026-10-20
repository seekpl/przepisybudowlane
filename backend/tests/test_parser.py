from __future__ import annotations

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
