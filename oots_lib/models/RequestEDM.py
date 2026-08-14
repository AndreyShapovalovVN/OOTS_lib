from dataclasses import asdict, dataclass


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
    if not isinstance(request, EDMRequest):
        raise TypeError(f"Очікувався EDMRequest, отримано {type(request).__name__}")

    value = [asdict(request)] if if_save_list else asdict(request)
    await redis_client.save_to_redis(key, value)


async def get_edm_request_from_redis(redis_client, key: str) -> EDMRequest | None:
    """
    Отримує EDMRequest з Redis та десеріалізує у модель.

    Args:
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для читання

    Returns:
        EDMRequest або None, якщо ключ відсутній
    """
    data = await redis_client.get_from_redis(key)
    if data is None:
        return None

    # Підтримка старого формату, де в Redis зберігається список
    if isinstance(data, list):
        if not data:
            return None
        data = data[0]

    if not isinstance(data, dict):
        raise ValueError(f"Некоректний формат EDMRequest у Redis: {type(data).__name__}")

    return _dict_to_edm_request(data)


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
