import logging
from typing import Any

import httpx

from oots_lib.import_env import import_env

_logger = logging.getLogger(__name__)

BASE_URL = import_env("EXCHANGE_LOGGER_URI")
API_KEY = import_env("EXCHANGE_LOGGER_API_KEY")

if not BASE_URL.startswith("https://"):
    _logger.warning(
        "EXCHANGE_LOGGER_URI не використовує HTTPS: API-ключ передається в незашифрованому вигляді"
    )


class LoggerServiceError(RuntimeError):
    """Не вдалося передати журнал транзакцій до сервісу журналювання."""


class ToLogger:
    def __init__(self, conversation_id: str):
        self.payload: dict[str, Any] = {
            "conversation_id": conversation_id,
            "calls": [],
        }
        # _logger.debug(self.payload)

    def append_calls(self, calls: dict):
        self.payload["calls"].append(calls)
        return self

    def send_to_logger(self):
        """Надсилає журнал транзакцій до сервісу журналювання.

        Raises:
            LoggerServiceError: Якщо запит не вдався або сервіс повернув помилку
        """
        _logger.debug("Запускаємо процес обміну з журналом...")
        _logger.debug(self.payload)

        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30.0) as client:
            try:
                r = client.post(
                    f"{BASE_URL}/logs/trembita", headers=headers, json=self.payload
                )
            except httpx.HTTPError as e:
                raise LoggerServiceError(f"Помилка надсилання журналу: {e}") from e

            _logger.debug(f"Відповідь сервісу журналювання: {r.status_code}, {r.text}")
            if r.is_error:
                raise LoggerServiceError(
                    f"Сервіс журналювання повернув {r.status_code}: {r.text}"
                )
        _logger.debug("Обмін із журналом завершено")
