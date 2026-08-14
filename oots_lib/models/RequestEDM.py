from dataclasses import asdict, dataclass

from oots_lib.lib.redis_serde import load_model_from_redis, save_model_to_redis


@dataclass
class EDMRequest:
    href: str
    MimeType: str   # NOSONAR
    content: str
    process_queue: str | None = None
    content2: str | None = None


__all__ = [
    "EDMRequest",
    "save_edm_request_to_redis",
    "get_edm_request_from_redis",
]


async def save_edm_request_to_redis(redis_client, key: str, request: EDMRequest, if_save_list: bool = True) -> None:
    """
    Зберігає EDMRequest до Redis як JSON.

    Args:
        if_save_list: В якому вигляді зберігати в Rediі по замоченню списком
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для збереження
        request: Об'єкт EDMRequest
    """
    await save_model_to_redis(
        redis_client,
        key,
        request,
        EDMRequest,
        to_dict=asdict,
        as_list=if_save_list,
    )


async def get_edm_request_from_redis(redis_client, key: str) -> EDMRequest | None:
    """
    Отримує EDMRequest з Redis та десеріалізує у модель.

    Args:
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для читання

    Returns:
        EDMRequest або None, якщо ключ відсутній
    """
    return await load_model_from_redis(
        redis_client, key, "EDMRequest", _dict_to_edm_request
    )


def _dict_to_edm_request(data: dict) -> EDMRequest:
    """Конвертує словник у EDMRequest."""
    try:
        return EDMRequest(
            href=data["href"],
            MimeType=data["MimeType"],
            content=data["content"],
            process_queue=data.get("process_queue"),
            content2=data.get("content2"),
        )
    except KeyError as e:
        raise ValueError(f"Відсутнє обов'язкове поле EDMRequest: {e}") from e
