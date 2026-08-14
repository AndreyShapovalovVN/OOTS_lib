import json
from typing import Any, cast

import pytest
import redis
from conftest import FakeAsyncRedisClient

import oots_lib.lib.UseRedis as use_redis
from oots_lib.lib.UseRedis import (
    KeyIsNone,
    UseRedisAsync,
    close_redis,
    get_redis_client,
    initialize_redis,
)


@pytest.fixture(autouse=True)
def reset_global_instance():
    use_redis._redis_instance = None
    yield
    use_redis._redis_instance = None


def wrapper_with(fake: FakeAsyncRedisClient, prefix: str | None = None) -> UseRedisAsync:
    wrapper = UseRedisAsync(redis_prefix=prefix)
    wrapper._redis_client = cast("Any", fake)
    return wrapper


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [(None, ""), ("", ""), ("  ", ""), ("app", "app:"), (":app:", "app:")],
)
def test_normalize_prefix(prefix, expected):
    assert UseRedisAsync._normalize_prefix(prefix) == expected


def test_prefixed_key_is_idempotent(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client, prefix="app")

    assert wrapper._prefixed_key("key") == "app:key"
    assert wrapper._prefixed_key("app:key") == "app:key"


def test_prefixed_key_without_prefix(fake_redis_client):
    assert wrapper_with(fake_redis_client)._prefixed_key("key") == "key"


def test_constructor_accepts_existing_client():
    client = redis.asyncio.Redis.from_url("redis://localhost:6379/0")
    assert UseRedisAsync(client).redis is client


def test_constructor_wraps_connection_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("нема з'єднання")

    monkeypatch.setattr(use_redis.Redis, "from_url", boom)

    with pytest.raises(redis.exceptions.ConnectionError, match="Не вдалося під'єднатись"):
        UseRedisAsync("redis://localhost:6379/0")


async def test_save_and_get_json_roundtrip_uses_prefix_and_ttl(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client, prefix="app")

    await wrapper.save_to_redis("key", {"a": 1})

    assert json.loads(fake_redis_client.storage["app:key"]) == {"a": 1}
    assert fake_redis_client.expirations["app:key"] == use_redis.TTL
    assert await wrapper.get_from_redis("key") == {"a": 1}


async def test_save_serializes_unsupported_types_as_str(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)
    await wrapper.save_to_redis("key", {"a": {1, 2}})

    assert isinstance(json.loads(fake_redis_client.storage["key"])["a"], str)


async def test_get_returns_none_for_missing_key(fake_redis_client):
    assert await wrapper_with(fake_redis_client).get_from_redis("key") is None


async def test_get_returns_none_for_invalid_json(fake_redis_client):
    fake_redis_client.storage["key"] = b"{not json"
    assert await wrapper_with(fake_redis_client).get_from_redis("key") is None


async def test_save_and_get_raw_bytes(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)

    await wrapper.save_raw_to_redis("key", b"%PDF")

    assert await wrapper.get_raw_from_redis("key") == b"%PDF"


async def test_get_raw_ignores_non_bytes_values(fake_redis_client):
    fake_redis_client.storage["key"] = "text"
    assert await wrapper_with(fake_redis_client).get_raw_from_redis("key") is None


async def test_save_raw_validates_data(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)

    with pytest.raises(ValueError, match="не можуть бути None"):
        await wrapper.save_raw_to_redis("key", None)
    with pytest.raises(ValueError, match="типу bytes"):
        await wrapper.save_raw_to_redis("key", "text")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "method_name",
    ["get_from_redis", "get_raw_from_redis", "get_flag", "pop_from_queue"],
)
async def test_none_key_raises(fake_redis_client, method_name):
    wrapper = wrapper_with(fake_redis_client)
    with pytest.raises(KeyIsNone):
        await getattr(wrapper, method_name)(None)


async def test_none_key_raises_on_writes(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)

    with pytest.raises(KeyIsNone):
        await wrapper.save_to_redis(None, {})
    with pytest.raises(KeyIsNone):
        await wrapper.save_raw_to_redis(None, b"x")
    with pytest.raises(KeyIsNone):
        await wrapper.set_flag(None, True)


async def test_queue_push_and_pop(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client, prefix="app")

    await wrapper.push_to_queue("queue", "message-1")

    assert fake_redis_client.queues["app:queue"] == ["message-1"]
    assert await wrapper.pop_from_queue("queue") == "message-1"
    assert await wrapper.pop_from_queue("queue") is None


async def test_pop_from_queue_as_tuple_string(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)
    await wrapper.push_to_queue("queue", "message-1")

    assert await wrapper.pop_from_queue("queue", return_tuple_as_string=True) == (
        "(queue, message-1)"
    )


async def test_pop_from_queue_swallows_timeout(fake_redis_client):
    fake_redis_client.brpop_timeout = True
    assert await wrapper_with(fake_redis_client).pop_from_queue("queue") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(b"true", True), (b"false", False)],
)
async def test_flag_roundtrip(fake_redis_client, value, expected):
    wrapper = wrapper_with(fake_redis_client)

    await wrapper.set_flag("flag", expected)

    assert fake_redis_client.storage["flag"] == value.decode()
    assert await wrapper.get_flag("flag") is expected


async def test_get_flag_defaults(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)

    assert await wrapper.get_flag("missing") is False
    assert await wrapper.get_flag("missing", default=True) is True


async def test_get_flag_default_for_non_boolean_and_invalid_json(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)
    fake_redis_client.storage["number"] = b"5"
    fake_redis_client.storage["broken"] = b"{"

    assert await wrapper.get_flag("number", default=True) is True
    assert await wrapper.get_flag("broken", default=True) is True


async def test_delete_from_redis(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client, prefix="app")
    await wrapper.save_to_redis("key", {"a": 1})

    await wrapper.delete_from_redis("key")

    assert "app:key" not in fake_redis_client.storage
    with pytest.raises(ValueError, match="не може бути None"):
        await wrapper.delete_from_redis(None)  # type: ignore[arg-type]


async def test_health_and_health_check_success(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)

    assert await wrapper.health() is True
    assert await wrapper.health_check() is True


async def test_health_check_raises_when_unavailable():
    wrapper = wrapper_with(FakeAsyncRedisClient(ping_error=RuntimeError("down")))

    assert await wrapper.health() is False
    with pytest.raises(redis.exceptions.ConnectionError, match="недоступний"):
        await wrapper.health_check()


async def test_disconnect_is_safe_without_close_methods(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)
    wrapper._redis_client = object()

    await wrapper.disconnect()


async def test_async_context_manager_returns_self(fake_redis_client):
    wrapper = wrapper_with(fake_redis_client)

    async with wrapper as entered:
        assert entered is wrapper


def test_get_redis_client_is_singleton():
    client = get_redis_client()
    assert get_redis_client() is client


async def test_initialize_redis_checks_health_and_replaces_instance(monkeypatch):
    fake = FakeAsyncRedisClient()

    def fake_from_url(*args, **kwargs):
        return fake

    monkeypatch.setattr(use_redis.Redis, "from_url", fake_from_url)

    wrapper = await initialize_redis("redis://localhost:6379/1")

    assert use_redis._redis_instance is wrapper
    assert get_redis_client() is wrapper


async def test_close_redis_clears_instance(monkeypatch):
    monkeypatch.setattr(use_redis.Redis, "from_url", lambda *a, **k: FakeAsyncRedisClient())

    await initialize_redis()
    await close_redis()

    assert use_redis._redis_instance is None
    await close_redis()
