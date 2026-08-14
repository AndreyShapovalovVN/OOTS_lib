# mypy: ignore-errors
import inspect
import json
import logging
import os
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import redis
import redis.asyncio as Redis
from redis.maint_notifications import MaintNotificationsConfig

from oots_lib.import_env import import_env

_logger = logging.getLogger(__name__)

REDIS_URL = import_env("REDIS_URL")
TTL = int(import_env("REDIS_TTL" ))
REDIS_PREFIX = import_env("REDIS_PREFIX", "")
REDIS_TIMEOUT = int(import_env("REDIS_TIMEOUT", "6"))

# Глобальний екземпляр для централізованого управління з'єднанням
_redis_instance: Optional["UseRedisAsync"] = None


class KeyIsNone(ValueError):
    """Виключення для випадків, коли ключ Redis є None."""


class RedisDataError(ValueError):
    """Дані у Redis мають некоректний формат і не можуть бути десеріалізовані."""


def mask_redis_url(url: str) -> str:
    """Приховує облікові дані у Redis URL для безпечного журналювання."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<redis-url>"
    if not parts.hostname:
        return "<redis-url>"
    netloc = parts.hostname
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    if parts.username or parts.password:
        netloc = f"***:***@{netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def get_redis_client() -> "UseRedisAsync":
    """Отримує глобальний екземпляр клієнта Redis (Singleton-патерн).

    Returns:
        Екземпляр UseRedisAsync

    Raises:
        redis.exceptions.ConnectionError: Якщо з'єднання з Redis не ініціалізовано
    """
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = UseRedisAsync()
    return _redis_instance


async def initialize_redis(redis_url: str | None = None) -> "UseRedisAsync":
    """Ініціалізує глобальне з'єднання Redis на старті додатка.

    Args:
        redis_url: URL для підключення. Якщо None використовує REDIS_URL з оточення

    Returns:
        Ініціалізований екземпляр UseRedisAsync

    Raises:
        redis.exceptions.ConnectionError: Якщо підключення не вдалось
    """
    global _redis_instance
    _redis_instance = UseRedisAsync(redis_url)
    await _redis_instance.health_check()
    _logger.info("Redis клієнт ініціалізований та перевірений")
    return _redis_instance


async def close_redis() -> None:
    """Закриває глобальне з'єднання Redis на завершення додатка."""
    global _redis_instance
    if _redis_instance is not None:
        await _redis_instance.disconnect()
        _redis_instance = None
        _logger.info("Redis з'єднання закрито")


class UseRedisAsync:
    """Клас для асинхронних операцій з Redis та обробки помилок.

    Attributes:
        _redis_client: Екземпляр асинхронного клієнта Redis
    """

    def __init__(
        self,
        redis_url: str | Redis.Redis | None = None,
        redis_prefix: str | None = None,
    ):
        self._redis_prefix = self._normalize_prefix(redis_prefix or REDIS_PREFIX)
        try:
            if isinstance(redis_url, Redis.Redis):
                self._redis_client = redis_url
            else:
                url = redis_url if isinstance(redis_url, str) else REDIS_URL
                _logger.debug(f"URL підключення Redis: {mask_redis_url(url)}")
                self._redis_client = Redis.from_url(
                    url,
                    protocol=3,
                    socket_timeout=REDIS_TIMEOUT + 5,
                    socket_connect_timeout=5,
                    maint_notifications_config=MaintNotificationsConfig(enabled=False),
                )
        except Exception as e:
            raise redis.exceptions.ConnectionError(
                f"Не вдалося під'єднатись до Redis: {e}"
            ) from e

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        clean_prefix = (prefix or "").strip().strip(":")
        return f"{clean_prefix}:" if clean_prefix else ""

    def _prefixed_key(self, key: str) -> str:
        if not self._redis_prefix or key.startswith(self._redis_prefix):
            return key
        return f"{self._redis_prefix}{key}"

    async def get_from_redis(self, key: str | None) -> dict | list | None:
        """Отримує та десеріалізує JSON дані з Redis за ключем.

        Args:
            key: Ключ Redis для отримання даних

        Returns:
            Десеріалізований словник або None, якщо ключ не існує

        Raises:
            KeyIsNone: Якщо ключ є None
            RedisDataError: Якщо значення за ключем не є валідним JSON
        """
        if key is None:
            raise KeyIsNone()

        redis_key = self._prefixed_key(key)
        data = await self._redis_client.get(redis_key)
        if data is None:
            return None
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise RedisDataError(
                f"Не вдалося розшифрувати JSON для ключа {redis_key}: {e}"
            ) from e
        _logger.debug(f"Отримано дані з Redis для ключа {redis_key}")
        return data

    async def get_raw_from_redis(self, key: str | None) -> bytes | None:
        """Отримує сирі bytes дані з Redis.

        Args:
            key: Ключ Redis для отримання сирих даних

        Returns:
            Сирі дані або None, якщо ключ не існує
        """
        if key is None:
            raise KeyIsNone

        redis_key = self._prefixed_key(key)
        data = await self._redis_client.get(redis_key)
        _logger.debug(
            f"Отримано сирі дані з Redis для ключа {redis_key}, "
            f"розмір: {len(data) if data else 0} байт"
        )
        return data if isinstance(data, bytes) else None

    async def save_to_redis(
        self, key: str | None, data: dict[Any, Any] | list | str
    ) -> None:
        """Зберігає дані як JSON до Redis з TTL.

        Args:
            key: Ключ Redis для зберігання даних
            data: Дані для серіалізації та зберігання
        """
        if key is None:
            raise KeyIsNone()

        redis_key = self._prefixed_key(key)
        await self._redis_client.set(redis_key, json.dumps(data, default=str), ex=TTL)
        _logger.debug(f"Збережено дані до Redis для ключа {redis_key}")

    async def save_raw_to_redis(self, key: str | None, data: bytes | None) -> None:
        """Зберігає сирі bytes дані до Redis з TTL.

        Args:
            key: Ключ Redis для зберігання сирих даних
            data: Сирі дані для зберігання
        """
        if key is None:
            raise KeyIsNone()
        if data is None:
            raise ValueError("Сирі дані не можуть бути None")
        if not isinstance(data, bytes):
            raise ValueError("Сирі дані повинні бути типу bytes")

        redis_key = self._prefixed_key(key)

        await self._redis_client.set(redis_key, data, ex=TTL)
        _logger.debug(
            f"Збережено сирі дані до Redis для ключа {redis_key}, "
            f"розмір: {len(data)} байт"
        )

    async def push_to_queue(self, queue_name: str, message: str) -> None:
        """Поміщає повідомлення до Redis-черги list.

        Args:
            queue_name: Назва черги Redis list
            message: Повідомлення для поміщення в чергу
        """
        redis_queue = self._prefixed_key(queue_name)
        await self._redis_client.lpush(redis_queue, message)
        _logger.debug(f"Поміщено повідомлення до черги {redis_queue}: {message}")

    async def set_flag(self, key: str | None, value: bool | None) -> None:
        """Зберігає булевий прапор до Redis з TTL.

        Args:
            key: Ключ Redis для зберігання прапора
            value: Булеве значення для зберігання

        Raises:
            KeyIsNone: Якщо ключ є None
        """
        if key is None:
            raise KeyIsNone()

        redis_key = self._prefixed_key(key)
        # Зберігаємо як JSON boolean: true/false
        flag_value = json.dumps(value)
        await self._redis_client.set(redis_key, flag_value, ex=TTL)
        _logger.debug(f"Встановлено прапор {redis_key} = {value}")

    async def get_flag(self, key: str | None, default: bool = False) -> bool:
        """Отримує булевий прапор з Redis.

        Args:
            key: Ключ Redis для отримання прапора
            default: Значення за замовчуванням, якщо прапор не знайдено

        Returns:
            Булеве значення прапора або default, якщо ключ не існує

        Raises:
            KeyIsNone: Якщо ключ є None
        """
        if key is None:
            raise KeyIsNone()

        redis_key = self._prefixed_key(key)
        data = await self._redis_client.get(redis_key)

        if data is None:
            _logger.debug(
                f"Прапор {redis_key} не знайдено, повертаємо default: {default}"
            )
            return default

        try:
            value = json.loads(data)
            if not isinstance(value, bool):
                _logger.warning(
                    f"Значення прапора {redis_key} не є boolean: {value}, повертаємо default"
                )
                return default
            _logger.debug(f"Отримано прапор {redis_key} = {value}")
            return value
        except json.JSONDecodeError as e:
            _logger.warning(
                f"Не вдалося розшифрувати булевий прапор {redis_key}: {e}, повертаємо default"
            )
            return default

    @staticmethod
    def _decode(value: Any) -> str:
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    async def pop_from_queue(
        self,
        queue_name: str | None = None,
        return_tuple_as_string: bool = False,
    ) -> str | None:
        if queue_name is None:
            raise KeyIsNone()

        redis_queue = self._prefixed_key(queue_name)

        try:
            result = await self._redis_client.brpop(
                [redis_queue], timeout=REDIS_TIMEOUT
            )
        except redis.exceptions.TimeoutError:
            _logger.debug(f"BRPOP таймаут по черзі {redis_queue}, черга порожня")
            return None

        if result is None:
            return None

        queue, payload = result

        if return_tuple_as_string:
            return f"({self._decode(queue)}, {self._decode(payload)})"

        return self._decode(payload)

    async def health(self) -> bool:
        """Перевіряє здоров'я з'єднання з Redis без виключень.

        Зручно використовувати в health-endpoint або умовних перевірках,
        коли важливо отримати bool без обробки виключень.

        Returns:
            True якщо з'єднання активне, False інакше
        """
        try:
            await self._redis_client.ping()
            _logger.debug("Redis здоров'я: OK")
            return True
        except Exception as e:
            _logger.warning(f"Redis недоступний: {e}")
            return False

    async def health_check(self) -> bool:
        """Перевіряє здоров'я з'єднання з Redis.

        На відміну від :meth:`health`, кидає виключення при невдачі —
        підходить для ініціалізації або критичних перевірок.

        Returns:
            True якщо з'єднання активне

        Raises:
            redis.exceptions.ConnectionError: Якщо з'єднання неможливе
        """
        if not await self.health():
            raise redis.exceptions.ConnectionError("Redis недоступний")
        return True

    async def disconnect(self) -> None:
        """Закриває з'єднання з Redis."""
        close_fn = getattr(self._redis_client, "aclose", None)
        if close_fn is None:
            close_fn = getattr(self._redis_client, "close", None)

        if close_fn is None:
            _logger.warning("Redis клієнт не має close/aclose")
            return

        try:
            close_result = close_fn()
            if inspect.isawaitable(close_result):
                await close_result
        except Exception as e:
            _logger.warning(f"Помилка при закритті Redis: {e}", exc_info=e)
            return
        _logger.debug("Redis з'єднання закрито")

    async def __aenter__(self) -> "UseRedisAsync":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    @property
    def redis(self) -> Redis.Redis:
        """Отримує екземпляр клієнта Redis.

        Returns:
            Екземпляр клієнта Redis
        """
        return self._redis_client

    async def delete_from_redis(self, key: str) -> None:
        """Видаляє ключ з Redis.

        Args:
            key: Ключ для видалення
        """
        if key is None:
            raise ValueError("Ключ не може бути None")

        redis_key = self._prefixed_key(key)
        await self._redis_client.delete(redis_key)
        _logger.debug(f"Видалено ключ з Redis: {redis_key}")
