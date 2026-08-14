"""Спільна (де)серіалізація моделей у Redis.

Модулі моделей використовують однакову схему збереження та читання:
JSON-словник (іноді загорнутий у список) під ключем Redis. Ці помічники
тримають цю схему в одному місці.
"""

from collections.abc import Callable
from typing import Any

__all__ = [
    "load_model_from_redis",
    "save_model_to_redis",
]


async def save_model_to_redis(
    redis_client: Any,
    key: str,
    model: Any,
    model_type: type,
    to_dict: Callable[[Any], Any],
    as_list: bool = False,
) -> None:
    """Зберігає модель до Redis як JSON.

    Args:
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для збереження
        model: Об'єкт моделі
        model_type: Очікуваний тип моделі
        to_dict: Функція серіалізації моделі у словник
        as_list: Чи загортати словник у список (легасі-формат)

    Raises:
        TypeError: Якщо модель не є екземпляром `model_type`
    """
    if not isinstance(model, model_type):
        raise TypeError(
            f"Очікувався {model_type.__name__}, отримано {type(model).__name__}"
        )

    payload = to_dict(model)
    await redis_client.save_to_redis(key, [payload] if as_list else payload)


async def load_model_from_redis[T](
    redis_client: Any,
    key: str,
    model_name: str,
    from_dict: Callable[[dict], T],
    error_message: str | None = None,
) -> T | None:
    """Читає модель з Redis і десеріалізує її.

    Args:
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для читання
        model_name: Назва моделі для повідомлень про помилки
        from_dict: Функція конвертації словника у модель
        error_message: Якщо задано, помилки конвертації загортаються
            у `ValueError` з цим префіксом

    Returns:
        Модель або None, якщо ключ відсутній

    Raises:
        ValueError: Якщо дані у Redis мають некоректний формат
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
        raise ValueError(
            f"Некоректний формат {model_name} у Redis: {type(data).__name__}"
        )

    try:
        return from_dict(data)
    except (KeyError, TypeError, ValueError) as e:
        if error_message is None:
            raise
        raise ValueError(f"{error_message}: {e}") from e
