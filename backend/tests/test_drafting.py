"""Szkice objaśnień AI (arkusz, 3.3–3.6): akapity źródła, walidatory, zadania, kolejka recenzenta, decyzja.

Claude API zastępuje atrapa z tą samą metodą ``beta.messages.create`` — testy nie łączą się z siecią.
"""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EditorialTask, Explanation, ExplanationVersion, LegalUnit
from app.modules.drafting import claude
from app.modules.drafting.diff import sentences
from app.modules.drafting.service import AI_AUTHOR, process_open
from app.modules.drafting.sources import Fragment, fragments
from app.modules.drafting.validators import Quote, Sentence, check
from tests.conftest import FIXTURES, NOW, FakeEli, only_act

PB_TEXT = "/eli/acts/DU/2026/524/text.html"
PKT_1A = "prawo-budowlane-art-29-ust-1-pkt-1a"
JAN = {"Authorization": "Bearer tok-jan"}  # recenzent
ANNA = {"Authorization": "Bearer tok-anna"}  # redaktor

INTRO = "Nie wymaga decyzji o pozwoleniu na budowę, ale wymaga zgłoszenia, o którym mowa w art. 30, budowa:"
POINT = (
    "wolno stojących, nie więcej niż dwukondygnacyjnych budynków mieszkalnych jednorodzinnych o powierzchni "
    "zabudowy do 90 m², których obszar oddziaływania mieści się w całości na działce"
)
SOURCES = [
    Fragment("A1", "art. 29 ust. 1", INTRO),
    Fragment("A2", "art. 29 ust. 1 pkt 1a", POINT),
]


def sentence(text: str, *quotes: tuple[str, str]) -> Sentence:
    return Sentence(text=text, quotes=[Quote(fragment_id=i, text=q) for i, q in quotes])


# --- Akapity źródła ---------------------------------------------------------------------------


def test_fragments_label_each_paragraph_with_its_provision() -> None:
    content = [
        {"unit": "Art. 29. 1.", "text": INTRO},
        {"unit": "1a)", "text": POINT},
    ]
    assert [(f.id, f.label) for f in fragments("art_29.ust_1.pkt_1a", content)] == [
        ("A1", "art. 29 ust. 1"),
        ("A2", "art. 29 ust. 1 pkt 1a"),
    ]
    wt = [{"unit": "§ 12. 1.", "text": "…"}, {"unit": "1)", "text": "4 m"}, {"unit": "2)", "text": "3 m"}]
    assert [f.label for f in fragments("par_12.ust_1", wt)] == [
        "§ 12 ust. 1",
        "§ 12 ust. 1 pkt 1",
        "§ 12 ust. 1 pkt 2",
    ]
    kpa = [{"unit": "Art. 10. § 1.", "text": "…"}, {"unit": "§ 2.", "text": "…"}]
    assert [f.label for f in fragments("art_10", kpa)] == ["art. 10 § 1", "art. 10 § 2"]


# --- Walidatory (3.4) -------------------------------------------------------------------------


def test_validators_accept_sentence_backed_by_verbatim_quote() -> None:
    [ok] = check(
        [
            sentence(
                "Dom o powierzchni zabudowy do 90 m² zbudujesz na zgłoszenie, o którym mowa w art. 30.",
                ("A1", "wymaga zgłoszenia, o którym mowa w art. 30"),
                ("A2", "o powierzchni zabudowy do 90 m²"),
            )
        ],
        SOURCES,
    )
    assert ok.ok, ok.errors


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        (sentence("Dom zbudujesz na zgłoszenie."), "bez cytatu"),
        (sentence("Dom zbudujesz na zgłoszenie.", ("A7", "wymaga zgłoszenia")), "spoza przepisu"),
        (sentence("Dom zbudujesz na zgłoszenie.", ("A1", "wymaga zgłoszenia budowy domu")), "dosłownie"),
        (sentence("Dom zbudujesz na zgłoszenie.", ("A1", "wymaga")), "za krótki"),
        # Liczba spoza tekstu (stare brzmienie albo zamiana słów na cyfry) — zdanie odpada.
        (sentence("Dom do 70 m² zbudujesz na zgłoszenie.", ("A2", "o powierzchni zabudowy do 90 m²")), "70"),
        (sentence("Dom może mieć 2 kondygnacje.", ("A2", "nie więcej niż dwukondygnacyjnych")), "2"),
        (sentence("Zgłoszenie opisuje art. 31.", ("A1", "o którym mowa w art. 30")), "art. 31"),
        (
            sentence(
                "Od 21 września 2026 r. wystarczy zgłoszenie.", ("A1", "wymaga zgłoszenia, o którym mowa")
            ),
            "września",
        ),
    ],
)
def test_validators_reject_unsupported_sentences(bad: Sentence, error: str) -> None:
    [checked] = check([bad], SOURCES)
    assert not checked.ok
    assert error in " ".join(checked.errors)


def test_reference_from_label_of_cited_paragraph_is_allowed() -> None:
    [ok] = check(
        [sentence("Tak stanowi art. 29 ust. 1 pkt 1a.", ("A2", "budynków mieszkalnych jednorodzinnych"))],
        SOURCES,
    )
    assert ok.ok, ok.errors


def test_sentence_split_keeps_legal_abbreviations() -> None:
    text = "Sprawdź art. 30 ust. 1. Zgłoszenie dotyczy np. Domu.\n\nTo drugi akapit (Dz. U. poz. 1)."
    assert sentences(text) == [
        "Sprawdź art. 30 ust. 1.",
        "Zgłoszenie dotyczy np. Domu.",
        "To drugi akapit (Dz. U. poz. 1).",
    ]


# --- Atrapa Claude API ------------------------------------------------------------------------


class FakeClaude:
    def __init__(self, *responses: dict[str, Any] | str) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if r == "refusal":
            return SimpleNamespace(stop_reason="refusal", content=[], model=kwargs["model"])
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(r, ensure_ascii=False))],
            model=kwargs["model"],
        )


GOOD = {
    "tekst": "Wolno stojący dom o powierzchni zabudowy do 90 m² zbudujesz bez pozwolenia na budowę.",
    "cytaty": [
        {"akapit": "A1", "cytat": "Nie wymaga decyzji o pozwoleniu na budowę"},
        {"akapit": "A2", "cytat": "o powierzchni zabudowy do 90 m"},
    ],
}
GOOD_2 = {
    "tekst": "Musisz jednak dokonać zgłoszenia, o którym mowa w art. 30.",
    "cytaty": [{"akapit": "A1", "cytat": "wymaga zgłoszenia, o którym mowa w art. 30"}],
}
STALE = {
    "tekst": "Dom może mieć do 70 m² powierzchni zabudowy.",
    "cytaty": [{"akapit": "A2", "cytat": "o powierzchni zabudowy do 90 m"}],
}
NO_QUOTE = {"tekst": "Zgłoszenie złożysz w starostwie.", "cytaty": []}
DRAFT = {"akapity": [{"zdania": [GOOD, STALE]}, {"zdania": [GOOD_2, NO_QUOTE]}], "uwagi": "Pominąłem organ."}


@pytest.fixture
def changed_pb(seeded: Session, make_sync, fake_eli: FakeEli, set_now) -> Session:  # type: ignore[no-untyped-def]
    """Opublikowane objaśnienie pkt 1a, potem nowe brzmienie w ELI (70 → 90 m²)."""
    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    html = (
        (FIXTURES / "DU_2026_524.html")
        .read_text(encoding="utf-8")
        .replace("do 70 m<sup>2</sup>", "do 90 m<sup>2</sup>")
    )
    fake_eli.routes[PB_TEXT] = (200, html.encode(), "text/html")
    fake_eli.set_json("/eli/changes/acts", [{"ELI": "DU/2026/524", "changeDate": "2026-10-20T10:30:00"}])
    set_now(NOW + timedelta(hours=1))
    assert make_sync().run().status == "sukces"
    seeded.expire_all()
    return seeded


def _unit(s: Session, slug: str) -> LegalUnit:
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == slug))
    assert unit is not None
    return unit


def _versions(s: Session, unit: LegalUnit) -> list[ExplanationVersion]:
    e = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    return sorted(e.versions, key=lambda v: v.version_no) if e else []


def test_source_change_suspends_explanation_and_queues_ai_draft(changed_pb: Session) -> None:
    s = changed_pb
    unit = _unit(s, PKT_1A)
    [published] = _versions(s, unit)
    assert published.state == "zawieszony"
    task = s.scalar(
        select(EditorialTask).where(EditorialTask.kind == "szkic_ai", EditorialTask.unit_id == unit.id)
    )
    assert task is not None and task.state == "otwarte"
    # Punkt 1 się nie zmienił — jego objaśnienie zostaje i nie dostaje szkicu.
    pkt1 = _unit(s, "prawo-budowlane-art-29-ust-1-pkt-1")
    assert [v.state for v in _versions(s, pkt1)] == ["opublikowany"]
    assert not s.scalar(
        select(EditorialTask).where(EditorialTask.kind == "szkic_ai", EditorialTask.unit_id == pkt1.id)
    )


def test_worker_drafts_with_citations_and_drops_unsupported_sentences(changed_pb: Session) -> None:
    s = changed_pb
    fake = FakeClaude(DRAFT)
    [draft] = process_open(s, fake, get_settings())

    # Wywołanie: schemat JSON, odmowy ponawiane przez API na modelu zastępczym, model z konfiguracji.
    [call] = fake.calls
    assert call["model"] == get_settings().ai_model
    assert call["fallbacks"] == "default" and claude.FALLBACK_BETA in call["betas"]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": claude.SCHEMA}
    message = call["messages"][0]["content"]
    assert '<akapit id="A2" przepis="art. 29 ust. 1 pkt 1a">' in message and "90 m²" in message
    assert "Poprzednie brzmienie" in message and "70 m²" in message  # do porównania, nie do cytowania
    assert "Poprzednie objaśnienie" in message

    s.expire_all()
    draft = s.get(ExplanationVersion, draft.id)
    assert draft.state == "recenzja" and draft.author == AI_AUTHOR and draft.ai_model
    assert draft.body == f"{GOOD['tekst']}\n\n{GOOD_2['tekst']}"
    assert draft.ai_sentences[0][0]["cytaty"][1]["przepis"] == "art. 29 ust. 1 pkt 1a"
    rejected = draft.ai_report["odrzucone"]
    assert [r["tekst"] for r in rejected] == [STALE["tekst"], NO_QUOTE["tekst"]]
    assert "70" in rejected[0]["bledy"][0] and "bez cytatu" in rejected[1]["bledy"][0]
    task = s.scalar(select(EditorialTask).where(EditorialTask.kind == "szkic_ai"))
    assert task.state == "zamkniete" and "kolejce recenzji" in task.resolution
    # Szkic nigdy nie publikuje się sam: karta nadal pokazuje zawieszone objaśnienie.
    assert _versions(s, _unit(s, PKT_1A))[0].state == "zawieszony"


def test_review_queue_shows_only_differences_and_reviewer_publishes_by_name(changed_pb: Session, api) -> None:  # type: ignore[no-untyped-def]
    s = changed_pb
    process_open(s, FakeClaude(DRAFT), get_settings())

    [item] = api.get("/api/v1/redakcja/szkice-ai", headers=JAN).json()
    assert item["przepis"] == "art. 29 ust. 1 pkt 1a"
    change = item["zmiana_przepisu"]
    assert {"typ": "usuniete", "tekst": "70"} in change and {"typ": "dodane", "tekst": "90"} in change
    added = [x for x in item["zmiana_objasnienia"] if x["typ"] == "dodane"]
    assert [x["tekst"] for x in added] == [GOOD["tekst"], GOOD_2["tekst"]]
    assert all(x["cytaty"] for x in added)
    assert any(x["typ"] == "usuniete" for x in item["zmiana_objasnienia"])  # zdania starego objaśnienia
    assert len(item["odrzucone"]) == 2 and item["uwagi"] == "Pominąłem organ."

    # Redaktor nie zatwierdza; recenzent — tak, z komentarzem i nazwiskiem.
    r = api.post(
        f"/api/v1/redakcja/szkice-ai/{item['id']}/decyzja",
        headers=ANNA,
        json={"accept": True, "comment": "Zgadza się."},
    )
    assert r.status_code == 403
    r = api.post(
        f"/api/v1/redakcja/szkice-ai/{item['id']}/decyzja",
        headers=JAN,
        json={"accept": True, "comment": "Zgodne z nowym brzmieniem pkt 1a."},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"id": item["id"], "stan": "opublikowany", "recenzent": "jan"}
    assert api.get("/api/v1/redakcja/szkice-ai", headers=JAN).json() == []

    card = api.get(f"/api/v1/przepisy/{PKT_1A}").json()
    explanation = card["explanation"]
    assert explanation["ai_assisted"] is True and explanation["reviewer"] == "jan"
    assert explanation["state"] == "opublikowany" and explanation["paragraphs"][0] == GOOD["tekst"]


def test_reviewer_rejects_draft_and_it_leaves_the_queue(changed_pb: Session, api) -> None:  # type: ignore[no-untyped-def]
    s = changed_pb
    [draft] = process_open(s, FakeClaude(DRAFT), get_settings())
    r = api.post(
        f"/api/v1/redakcja/szkice-ai/{draft.id}/decyzja",
        headers=JAN,
        json={"accept": False, "comment": "Pomija warunek własnych potrzeb mieszkaniowych."},
    )
    assert r.status_code == 200 and r.json()["stan"] == "szkic"
    assert api.get("/api/v1/redakcja/szkice-ai", headers=JAN).json() == []
    s.expire_all()
    assert _versions(s, _unit(s, PKT_1A))[0].state == "zawieszony"


def test_refusal_keeps_task_open_and_gives_up_after_three_attempts(changed_pb: Session) -> None:
    s = changed_pb
    fake = FakeClaude("refusal", "refusal", "refusal")
    for attempt in (1, 2, 3):
        assert process_open(s, fake, get_settings()) == []
        task = s.scalar(select(EditorialTask).where(EditorialTask.kind == "szkic_ai"))
        assert task.details["proby"] == attempt and "odmówił" in task.details["ostatni_blad"]
    assert task.state == "zamkniete" and "napisze redaktor" in task.resolution
    assert len(_versions(s, _unit(s, PKT_1A))) == 1


def test_all_sentences_rejected_means_no_draft(changed_pb: Session) -> None:
    s = changed_pb
    assert (
        process_open(s, FakeClaude({"akapity": [{"zdania": [STALE, NO_QUOTE]}], "uwagi": ""}), get_settings())
        == []
    )
    task = s.scalar(select(EditorialTask).where(EditorialTask.kind == "szkic_ai"))
    assert task.state == "zamkniete" and "Walidatory odrzuciły" in task.resolution
    assert len(task.details["raport"]["odrzucone"]) == 2
    assert len(_versions(s, _unit(s, PKT_1A))) == 1


def test_editor_requests_draft_for_unit_without_explanation(seeded: Session, api) -> None:  # type: ignore[no-untyped-def]
    slug = "prawo-budowlane-art-29-ust-1-pkt-2"
    r = api.post("/api/v1/redakcja/szkice-ai", headers=ANNA, json={"unit_slug": slug})
    assert r.status_code == 202, r.text
    again = api.post("/api/v1/redakcja/szkice-ai", headers=ANNA, json={"unit_slug": slug})
    assert again.json()["zadanie"] == r.json()["zadanie"]  # jedno zadanie na brzmienie
    assert api.post("/api/v1/redakcja/szkice-ai", headers=JAN, json={"unit_slug": slug}).status_code == 403

    good = {
        "tekst": "Sprawdź, czego dotyczy ten punkt.",
        "cytaty": [{"akapit": "A1", "cytat": "Nie wymaga decyzji o pozwoleniu na budowę"}],
    }
    [draft] = process_open(seeded, FakeClaude({"akapity": [{"zdania": [good]}], "uwagi": ""}), get_settings())
    assert draft.version_no == 1 and draft.title == "Co to znaczy w praktyce"
    [item] = api.get("/api/v1/redakcja/szkice-ai", headers=JAN).json()
    assert item["zmiana_przepisu"] is None and item["poprzednie_objasnienie"] is None
    assert [x["typ"] for x in item["zmiana_objasnienia"]] == ["dodane"]


# --- Prawdziwe SDK Anthropic na podstawionym transporcie HTTP (bez sieci) ------------------------


def _sdk_client(handler: Any) -> Any:
    import anthropic
    import httpx2  # SDK 2.x używa httpx2, nie httpx

    return anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )


def test_sdk_request_shape_and_response_parsing() -> None:
    import httpx2

    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["beta"] = request.headers.get("anthropic-beta", "")
        seen["body"] = json.loads(request.content)
        message = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": seen["body"]["model"],
            "content": [{"type": "text", "text": json.dumps({"akapity": [{"zdania": [GOOD]}], "uwagi": ""})}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        return httpx2.Response(200, json=message)

    out = claude.draft(_sdk_client(handler), model="claude-opus-5-5", effort="high", message="Przepis…")
    assert seen["path"] == "/v1/messages" and claude.FALLBACK_BETA in seen["beta"]
    body = seen["body"]
    assert body["fallbacks"] == "default" and body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": claude.SCHEMA},
    }
    assert body["max_tokens"] == claude.MAX_TOKENS and body["system"] == claude.SYSTEM
    assert out.model == "claude-opus-5-5" and out.paragraphs[0][0].text == GOOD["tekst"]


@pytest.mark.parametrize(("status", "text"), [(429, "Limit zapytań"), (500, "błąd 500"), (400, "błąd 400")])
def test_sdk_errors_become_draft_errors(status: int, text: str) -> None:
    import httpx2

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json={"type": "error", "error": {"type": "api_error", "message": "x"}})

    with pytest.raises(claude.DraftError, match=text):
        claude.draft(_sdk_client(handler), model="claude-opus-5-5", effort="high", message="Przepis…")
