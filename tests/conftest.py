"""Shared fixtures and a minimal in-memory Redis double for the test suite."""

import os
from typing import Any

import pytest

# Модулі бібліотеки читають конфігурацію під час імпорту, тому змінні
# оточення мають бути встановлені до першого імпорту `oots_lib.*`.
_TEST_ENV = {
    "COUNTRY": "UA",
    "REDIS_URL": "redis://localhost:6379/0",
    "REDIS_TTL": "60",
    "REDIS_PREFIX": "",
    "REDIS_TIMEOUT": "1",
    "EXCHANGE_LOGGER_URI": "http://logger.local",
    "EXCHANGE_LOGGER_API_KEY": "test-api-key",
    "QUEUE_OUTCOMING": "oots:queue:outcoming",
    "IF_PREVIEW": "false",
    "TREMBITA_URL": "http://trembita.local",
    "TREMBITA_CLIENT_ID": "client-id",
    "TREMBITA_CACHE": "3600",
}

for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)


class FakeAsyncRedisClient:
    """Асинхронний двійник `redis.asyncio.Redis` з мінімальним API."""

    def __init__(self, ping_error: Exception | None = None):
        self.storage: dict[str, Any] = {}
        self.queues: dict[str, list[Any]] = {}
        self.expirations: dict[str, int | None] = {}
        self.ping_error = ping_error
        self.brpop_timeout = False
        self.closed = False

    async def get(self, key: str):
        return self.storage.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None):
        self.storage[key] = value
        self.expirations[key] = ex

    async def delete(self, key: str):
        self.storage.pop(key, None)

    async def lpush(self, queue: str, message: Any):
        self.queues.setdefault(queue, []).insert(0, message)

    async def brpop(self, queues: list[str], timeout: int = 0):
        if self.brpop_timeout:
            import redis

            raise redis.exceptions.TimeoutError("timeout")
        for queue in queues:
            items = self.queues.get(queue)
            if items:
                return queue.encode(), items.pop().encode()
        return None

    async def ping(self):
        if self.ping_error is not None:
            raise self.ping_error
        return True

    async def aclose(self):
        self.closed = True


@pytest.fixture
def fake_redis_client():
    return FakeAsyncRedisClient()


@pytest.fixture
def redis_wrapper(fake_redis_client):
    """`UseRedisAsync`, підключений до in-memory двійника."""
    from oots_lib.lib.UseRedis import UseRedisAsync

    wrapper = UseRedisAsync()
    wrapper._redis_client = fake_redis_client
    return wrapper
