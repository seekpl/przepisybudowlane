from __future__ import annotations

import httpx
import pytest

from app.modules.eli.client import EliClient, EliError, EliNotFound, EliUnavailable
from app.modules.eli.schemas import ActMetadata
from tests.conftest import FIXTURES


def client_for(responses: list[httpx.Response | Exception]) -> tuple[EliClient, list[float], list[str]]:
    sleeps: list[float] = []
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    c = EliClient(
        "https://api.example.test/eli",
        transport=httpx.MockTransport(handler),
        max_retries=3,
        backoff=1.0,
        sleep=sleeps.append,
    )
    return c, sleeps, calls


def test_retries_server_errors_with_growing_backoff_then_succeeds() -> None:
    c, sleeps, calls = client_for(
        [httpx.Response(503), httpx.Response(502), httpx.Response(200, json={"ok": True})]
    )
    r = c.get("/acts/DU/1994/414")
    assert r.status == 200
    assert sleeps == [1.0, 2.0]
    assert len(calls) == 3


def test_timeout_after_all_retries_raises_unavailable() -> None:
    c, sleeps, _ = client_for([httpx.ReadTimeout("timeout")] * 4)
    with pytest.raises(EliUnavailable) as exc:
        c.get("/acts/DU/1994/414")
    assert "4 próbach" in str(exc.value)
    assert sleeps == [1.0, 2.0, 4.0]


def test_not_found_is_not_retried() -> None:
    c, sleeps, calls = client_for([httpx.Response(404)])
    with pytest.raises(EliNotFound):
        c.get("/acts/DU/1994/1")
    assert sleeps == [] and len(calls) == 1


def test_client_error_is_not_retried() -> None:
    c, sleeps, _ = client_for([httpx.Response(400)])
    with pytest.raises(EliError):
        c.get("/acts/DU/x/1")
    assert sleeps == []


def test_rate_limit_is_retried() -> None:
    c, sleeps, _ = client_for([httpx.Response(429), httpx.Response(200, json={})])
    assert c.get("/changes/acts").status == 200
    assert sleeps == [1.0]


def test_metadata_schema_reads_fixture_and_reference_roles() -> None:
    meta = ActMetadata.model_validate_json((FIXTURES / "DU_1994_414.json").read_bytes())
    assert meta.eli == "DU/1994/414"
    assert meta.in_force == "IN_FORCE"
    assert [r.id for r in meta.refs("consolidated_texts")] == ["DU/2024/725", "DU/2026/524"]
    assert [r.id for r in meta.refs("amended_by")] == ["DU/2019/50", "DU/2025/100", "DU/2026/900"]


def test_metadata_without_required_fields_is_rejected() -> None:
    with pytest.raises(ValueError):
        ActMetadata.model_validate({"ELI": "DU/1994/414", "publisher": "DU"})


def test_unexpected_eli_shape_is_rejected() -> None:
    with pytest.raises(ValueError):
        ActMetadata.model_validate(
            {"ELI": "nonsense", "publisher": "DU", "year": 1, "pos": 1, "title": "t", "status": "s"}
        )
