import asyncio

import pytest

from oots_lib.lib.exception import KEYS, EDMException


class RedisSpy:
    def __init__(self, save_error: Exception | None = None, push_error: Exception | None = None):
        self.save_error = save_error
        self.push_error = push_error
        self.saved: list[tuple[str, dict]] = []
        self.pushed: list[tuple[str, str]] = []

    async def save_to_redis(self, key, data):
        if self.save_error is not None:
            raise self.save_error
        self.saved.append((key, data))

    async def push_to_queue(self, queue, message):
        if self.push_error is not None:
            raise self.push_error
        self.pushed.append((queue, message))


def make_exception(redis, **overrides) -> EDMException:
    kwargs = {
        "redis": redis,
        "queue": "queue-1",
        "key": "key-1",
        "message_id": "msg-1",
        "code": "EDM:ERR:0004",
        "message": "Не знайдено",
        "detail": "деталі",
    }
    kwargs.update(overrides)
    return EDMException(**kwargs)


def test_message_formatting_and_attributes():
    exc = make_exception(RedisSpy(), preview_link="https://preview")

    assert str(exc) == "[EDM:ERR:0004] Не знайдено: деталі"
    assert exc.queue == "queue-1"
    assert exc.key == "key-1"
    assert exc.preview_link == "https://preview"


def test_defaults_fall_back_to_env_queue_and_generated_key():
    exc = make_exception(RedisSpy(), queue=None, key=None)

    assert exc.queue == EDMException.QUEUE_OUTCOMING
    assert exc.key == KEYS.get_response_exp("msg-1")


def test_sync_context_runs_side_effects_immediately():
    redis = RedisSpy()

    make_exception(redis)

    assert redis.saved == [
        (
            "key-1",
            {
                "exception": {
                    "code": "EDM:ERR:0004",
                    "message": "Не знайдено",
                    "detail": "деталі",
                    "preview_link": None,
                }
            },
        )
    ]
    assert redis.pushed == [("queue-1", "msg-1")]


async def test_async_context_schedules_side_effects_as_task():
    redis = RedisSpy()

    make_exception(redis)

    assert redis.saved == []
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(redis.saved) == 1
    assert redis.pushed == [("queue-1", "msg-1")]


def test_redis_save_failure_does_not_break_construction():
    redis = RedisSpy(save_error=RuntimeError("redis down"))

    exc = make_exception(redis)

    assert exc.code == "EDM:ERR:0004"
    assert redis.pushed == [("queue-1", "msg-1")]


def test_queue_push_failure_does_not_break_construction():
    redis = RedisSpy(push_error=RuntimeError("queue down"))

    exc = make_exception(redis)

    assert exc.code == "EDM:ERR:0004"
    assert len(redis.saved) == 1


def test_is_raisable():
    with pytest.raises(EDMException, match="EDM:ERR:0004"):
        raise make_exception(RedisSpy())
