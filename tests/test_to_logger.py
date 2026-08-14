import httpx
import pytest

import oots_lib.lib.toLogger as to_logger_module
from oots_lib.lib.toLogger import LoggerServiceError, ToLogger


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "ok"):
        self.status_code = status_code
        self.text = text

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400


class FakeClient:
    def __init__(self, error: Exception | None = None, response: FakeResponse | None = None):
        self.error = error
        self.response = response or FakeResponse()
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
        return self.response


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


def test_send_to_logger_raises_on_transport_error(monkeypatch):
    client = FakeClient(error=httpx.ConnectError("недоступний"))
    monkeypatch.setattr(to_logger_module.httpx, "Client", lambda timeout=None: client)

    with pytest.raises(LoggerServiceError, match="Помилка надсилання журналу"):
        ToLogger("conv-1").send_to_logger()
    assert client.closed is True


def test_send_to_logger_raises_on_error_status(monkeypatch):
    client = FakeClient(response=FakeResponse(status_code=500, text="boom"))
    monkeypatch.setattr(to_logger_module.httpx, "Client", lambda timeout=None: client)

    with pytest.raises(LoggerServiceError, match="повернув 500"):
        ToLogger("conv-1").send_to_logger()
    assert client.closed is True
