import pytest

from oots_lib.models.RequestEDM import (
    EDMRequest,
    _dict_to_edm_request,
    get_edm_request_from_redis,
    save_edm_request_to_redis,
)


class RedisStub:
    def __init__(self, value=None):
        self.value = value
        self.saved: list[tuple[str, object]] = []

    async def save_to_redis(self, key, value):
        self.saved.append((key, value))

    async def get_from_redis(self, key):
        return self.value


def make_request() -> EDMRequest:
    return EDMRequest(href="cid:1@gov.ua", MimeType="application/xml", content="<a/>")


async def test_save_wraps_into_list_by_default():
    redis = RedisStub()
    await save_edm_request_to_redis(redis, "key", make_request())

    key, value = redis.saved[0]
    assert key == "key"
    assert value == [
        {
            "href": "cid:1@gov.ua",
            "MimeType": "application/xml",
            "content": "<a/>",
            "process_queue": None,
            "content2": None,
        }
    ]


async def test_save_as_plain_dict():
    redis = RedisStub()
    await save_edm_request_to_redis(redis, "key", make_request(), if_save_list=False)

    _, value = redis.saved[0]
    assert isinstance(value, dict)
    assert value["href"] == "cid:1@gov.ua"


async def test_save_rejects_wrong_type():
    with pytest.raises(TypeError, match="EDMRequest"):
        await save_edm_request_to_redis(RedisStub(), "key", {"href": "x"})  # type: ignore[arg-type]


async def test_roundtrip_through_redis():
    redis = RedisStub()
    request = EDMRequest(
        href="cid:1@gov.ua",
        MimeType="application/xml",
        content="<a/>",
        process_queue="queue",
        content2="<b/>",
    )
    await save_edm_request_to_redis(redis, "key", request)
    redis.value = redis.saved[0][1]

    assert await get_edm_request_from_redis(redis, "key") == request


async def test_get_returns_none_for_missing_key_and_empty_list():
    assert await get_edm_request_from_redis(RedisStub(None), "key") is None
    assert await get_edm_request_from_redis(RedisStub([]), "key") is None


async def test_get_accepts_plain_dict_format():
    data = {"href": "cid:1@gov.ua", "MimeType": "application/xml", "content": "<a/>"}
    request = await get_edm_request_from_redis(RedisStub(data), "key")

    assert request == make_request()


async def test_get_rejects_unexpected_payload():
    with pytest.raises(ValueError, match="str"):
        await get_edm_request_from_redis(RedisStub("not-a-dict"), "key")


def test_dict_to_edm_request_requires_mandatory_fields():
    with pytest.raises(ValueError, match="MimeType"):
        _dict_to_edm_request({"href": "cid:1@gov.ua", "content": "<a/>"})
