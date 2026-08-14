import httpx
import pytest

import oots_lib.lib.toLogger as to_logger_module
from oots_lib.lib.toLogger import ToLogger


class FakeResponse:
    status_code = 200
    text = "ok"


class FakeClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []
        self.timeout: float | None = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if self.error is not None:
            raise self.error
        return FakeResponse()


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()

    def factory(timeout=None):
        client.timeout = timeout
        return client

    monkeypatch.setattr(to_logger_module.httpx, "Client", factory)
    return client


def test_payload_initialized_with_conversation_id():
    logger = ToLogger("conv-1")
    assert logger.payload == {"conversation_id": "conv-1", "calls": []}


def test_append_calls_is_chainable():
    logger = ToLogger("conv-1")

    result = logger.append_calls({"a": 1}).append_calls({"b": 2})

    assert result is logger
    assert logger.payload["calls"] == [{"a": 1}, {"b": 2}]


def test_send_to_logger_posts_payload(fake_client):
    logger = ToLogger("conv-1").append_calls({"dataservice": "svc"})

    logger.send_to_logger()

    assert fake_client.timeout == 30.0
    assert fake_client.closed is True
    call = fake_client.calls[0]
    assert call["url"] == f"{to_logger_module.BASE_URL}/logs/trembita"
    assert call["headers"] == {
        "X-API-Key": to_logger_module.API_KEY,
        "Content-Type": "application/json",
    }
    assert call["json"] == logger.payload


def test_send_to_logger_swallows_transport_errors(monkeypatch):
    client = FakeClient(error=httpx.ConnectError("недоступний"))
    monkeypatch.setattr(to_logger_module.httpx, "Client", lambda timeout=None: client)

    assert ToLogger("conv-1").send_to_logger() is None
    assert client.closed is True
