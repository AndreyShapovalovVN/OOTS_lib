import logging
from typing import Any

import httpx
from oots_lib.import_env import import_env


_logger = logging.getLogger(__name__)

BASE_URL = import_env("EXCHANGE_LOGGER_URI")
API_KEY = import_env("EXCHANGE_LOGGER_API_KEY")


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
            except Exception as e:
                _logger.exception(f"Помилка надсилання журналу: {e}")
                return
            _logger.debug(f"Відповідь сервісу журналювання: {r.status_code}, {r.text}")
        _logger.debug("Обмін із журналом завершено")
