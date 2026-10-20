from __future__ import annotations

import pytest

from app.modules.search.stemmer import fold, stem

GROUPS = [
    ["płot", "płotu", "płoty", "płotem", "plot"],
    ["ogrodzenie", "ogrodzenia", "ogrodzeniem", "ogrodzeń", "ogrodzeniu"],
    ["granica", "granicy", "granicę", "granic", "granicą", "granicach"],
    ["budynek", "budynku", "budynki", "budynków", "budynkiem", "budynkach"],
    ["działka", "działki", "działkę", "działek", "dzialka"],
    ["pozwolenie", "pozwolenia", "pozwoleniu", "pozwoleń", "pozwoleniem"],
    ["zgłoszenie", "zgłoszenia", "zgloszenie", "zgłoszeniu"],
    ["odległość", "odległości", "odleglosc"],
    ["dom", "domu", "domy", "domem", "domów"],
    ["wiata", "wiaty", "wiatę"],
    ["inwestor", "inwestora", "inwestorowi", "inwestorem"],
    ["kierownik", "kierownika", "kierownikiem"],
]


@pytest.mark.parametrize("words", GROUPS, ids=[g[0] for g in GROUPS])
def test_inflected_forms_share_a_stem(words: list[str]) -> None:
    assert len({stem(w) for w in words}) == 1


def test_fold_removes_polish_diacritics() -> None:
    assert fold("Źdźbło łąki ŻÓŁĆ") == "zdzblo laki zolc"


def test_abbreviations_are_kept() -> None:
    assert stem("pkt") == "pkt"
    assert stem("MPZP") == "mpzp"
