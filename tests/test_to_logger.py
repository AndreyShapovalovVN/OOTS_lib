import httpx
import pytest

import oots_lib.lib.toLogger as to_logger_module
from oots_lib.lib.toLogger import ToLogger


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "ok"):
        self.status_code = status_code
        self.text = text

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
def fake_post(monkeypatch):
    calls: list[dict] = []

    def factory(url, *, headers=None, json=None, timeout=None):
        calls.append({
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        return FakeResponse()

    monkeypatch.setattr(to_logger_module.httpx, "post", factory)
    return calls


def test_payload_initialized_with_conversation_id():
    logger = ToLogger("conv-1")
    assert logger.payload == {"conversation_id": "conv-1", "calls": []}


def test_append_calls_is_chainable():
    logger = ToLogger("conv-1")

    result = logger.append_calls({"a": 1}).append_calls({"b": 2})

    assert result is logger
    assert logger.payload["calls"] == [{"a": 1}, {"b": 2}]


def test_send_to_logger_posts_payload(fake_post):
    logger = ToLogger("conv-1").append_calls({"dataservice": "svc"})

    logger.send_to_logger()

    assert len(fake_post) == 1
    call = fake_post[0]
    assert call["url"] == f"{to_logger_module.TraceabilityLogger().base_url}/logs/trembita"
    assert call["headers"] == {
        "X-API-Key": to_logger_module.TraceabilityLogger().api_key,
        "Content-Type": "application/json",
    }
    assert call["json"] == logger.payload
    assert call["timeout"] == 30.0
