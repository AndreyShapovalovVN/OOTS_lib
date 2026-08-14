import datetime

import pytest

import oots_lib.Transport as transport_module
from oots_lib.lib.exception import EDMException
from oots_lib.Transport import SOAPTransport


class RedisSpy:
    def __init__(self):
        self.saved: dict = {}
        self.pushed: list[tuple[str, str]] = []

    async def save_to_redis(self, key, value):
        self.saved[key] = value

    async def push_to_queue(self, queue, message):
        self.pushed.append((queue, message))


class FakeHistory:
    transaction_date = datetime.datetime(2024, 5, 1, 12, 0)
    transaction_id = "tx-1"


class FakeXClient:
    id = "trembita-msg-1"

    def __init__(self, *args, response=None, error=None, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.response = response
        self.error = error
        self.requests: list[dict] = []

    def request(self, **payload):
        self.requests.append(payload)
        if self.error is not None:
            raise self.error
        return self.response


class FakeToLogger:
    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.payload = {"conversation_id": conversation_id, "calls": []}
        self.sent = 0
        self.send_error: Exception | None = None

    def append_calls(self, calls):
        self.payload["calls"].append(calls)
        return self

    def send_to_logger(self):
        self.sent += 1
        if self.send_error is not None:
            raise self.send_error


class Service(SOAPTransport):
    def parsing_response(self, responce: dict) -> list[dict]:
        return [{"parsed": responce}]


@pytest.fixture
def transport_env(monkeypatch):
    redis = RedisSpy()
    created: dict = {}

    def client_factory(*args, **kwargs):
        client = FakeXClient(*args, **kwargs)
        created["client"] = client
        return client

    monkeypatch.setattr(transport_module, "XClient", client_factory)
    monkeypatch.setattr(transport_module, "RedisCache", lambda *a, **k: object())
    monkeypatch.setattr(transport_module, "Transport", lambda *a, **k: object())
    monkeypatch.setattr(transport_module, "UXPHistoryPlugin", FakeHistory)
    monkeypatch.setattr(transport_module, "ToLogger", FakeToLogger)
    monkeypatch.setattr(transport_module, "get_redis_client", lambda: redis)
    created["redis"] = redis
    return created


def test_abstract_parsing_response_required(transport_env):
    with pytest.raises(TypeError):
        SOAPTransport("svc", "conv-1")  # type: ignore[abstract]


def test_client_is_created_with_configured_service(transport_env):
    service = Service("GetDocuments", "conv-1")

    assert service.service == "GetDocuments"
    assert service.conversation_id == "conv-1"
    assert service.redis is transport_env["redis"]
    assert service.client is transport_env["client"]
    assert service.client.args[0] == transport_module.TREMBITA_URL
    assert service.client.kwargs["client"] == transport_module.TREMBITA_CLIENT_ID
    assert service.client.kwargs["service"] == "GetDocuments"


def test_client_creation_failure_raises_edm_exception(monkeypatch, transport_env):
    def boom(*args, **kwargs):
        raise RuntimeError("no route")

    monkeypatch.setattr(transport_module, "XClient", boom)

    with pytest.raises(EDMException, match="EDM:ERR:0006"):
        Service("GetDocuments", "conv-1")


def test_send_error_message_is_silent_when_disabled(transport_env):
    service = Service("GetDocuments", "conv-1", if_send_error=False)

    assert service.send_error_message(code="c", message="m", detail="d") is None
    assert transport_env["redis"].pushed == []


def test_send_error_message_saves_and_pushes(transport_env):
    service = Service("GetDocuments", "conv-1")

    with pytest.raises(EDMException, match=r"\[EDM:ERR:0004\]"):
        service.send_error_message(code="EDM:ERR:0004", message="m", detail="d")

    assert transport_env["redis"].pushed
    assert transport_env["redis"].saved


def test_response_returns_parsed_body_and_logs_transaction(transport_env):
    service = Service("GetDocuments", "conv-1")
    service.client.response = {"body": {"result": 1}}

    result = service.response({"query": "value"})

    assert result == [{"parsed": {"result": 1}}]
    assert service.client.requests == [{"query": "value"}]
    assert service.to_logger.sent == 1
    assert service.to_logger.payload["calls"] == [
        {
            "dataservice": "GetDocuments",
            "timestamp": "2024-05-01T12:00:00",
            "trembita_msg_id": "trembita-msg-1",
            "transaction_id": "tx-1",
        }
    ]


def test_response_raises_edm_exception_on_request_failure(transport_env):
    service = Service("GetDocuments", "conv-1")
    service.client.error = RuntimeError("timeout")

    with pytest.raises(EDMException, match="EDM:ERR:0006"):
        service.response({"query": "value"})


def test_response_raises_edm_exception_on_malformed_body(transport_env):
    service = Service("GetDocuments", "conv-1")
    service.client.response = {"unexpected": True}

    with pytest.raises(EDMException, match="некоректну структуру"):
        service.response({"query": "value"})


def test_logging_transaction_skipped_without_logger(transport_env):
    service = Service("GetDocuments", "conv-1")
    service.to_logger = None

    service._logging_trembita_transaction()


def test_logging_transaction_swallows_logger_errors(transport_env):
    service = Service("GetDocuments", "conv-1")
    service.to_logger.send_error = RuntimeError("logger down")

    service._logging_trembita_transaction()

    assert service.to_logger.sent == 1
