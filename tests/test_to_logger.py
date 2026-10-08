import httpx
import pytest

import oots_lib.lib.toLogger as to_logger_module
from oots_lib.lib.toLogger import TraceabilityLogger, build_trembita_payload


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "ok"):
        self.status_code = status_code
        self.text = text

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://logger.local/logs/trembita")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError(
                f"{self.status_code} {self.text}",
                request=request,
                response=response,
            )


@pytest.fixture
def fake_request(monkeypatch):
    calls: list[dict] = []

    def factory(method, url, *, headers=None, json=None, timeout=None):
        calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        return FakeResponse()

    monkeypatch.setattr(to_logger_module.httpx, "request", factory)
    return calls


def test_build_trembita_payload_initialized_with_conversation_id():
    payload = build_trembita_payload("conv-1")
    assert payload == {"conversation_id": "conv-1", "calls": []}


def test_log_trembita_sync_posts_payload(fake_request):
    payload = build_trembita_payload("conv-1")
    payload["calls"].append({"dataservice": "svc"})
    logger = TraceabilityLogger()

    assert logger.log_trembita_sync(payload) is True
    assert len(fake_request) == 1
    call = fake_request[0]
    assert call["method"] == "POST"
    assert call["url"] == f"{to_logger_module.TraceabilityLogger().base_url}/logs/trembita"
    assert call["headers"] == {
        "X-API-Key": to_logger_module.TraceabilityLogger().api_key,
        "Content-Type": "application/json",
    }
    assert call["json"] == payload
    assert call["timeout"] == 30.0


def test_log_trembita_sync_normalizes_non_serializable_values(fake_request):
    class SubmitResponse:
        def __str__(self) -> str:
            return "submitResponse(id=abc)"

    payload = build_trembita_payload("conv-1")
    payload["calls"].append({"raw_response": SubmitResponse()})
    logger = TraceabilityLogger()

    assert logger.log_trembita_sync(payload) is True
    call = fake_request[0]
    assert call["json"]["calls"][0]["raw_response"] == "submitResponse(id=abc)"
