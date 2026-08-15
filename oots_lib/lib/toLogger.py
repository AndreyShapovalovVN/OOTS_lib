import asyncio
import logging
from typing import Any

import httpx
from lxml import etree
from pyRegRep4.RIMParsing import Parsing  # type: ignore

from oots_lib.import_env import import_env
from oots_lib.models.Person import Person

_logger = logging.getLogger(__name__)

BASE_URL = import_env("EXCHANGE_LOGGER_URI")
API_KEY = import_env("EXCHANGE_LOGGER_API_KEY")

HEADERS: dict[str, str] = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

if not BASE_URL.startswith("https://"):
    _logger.warning(
        "EXCHANGE_LOGGER_URI не використовує HTTPS: API-ключ передається в незашифрованому вигляді"
    )


def agent_identifire(agent: etree._Element):
    ns = agent.nsmap
    identifire = agent.find(".//sdg:Identifier", namespaces=ns)  # type: ignore
    if identifire is None:
        return None, None
    _logger.debug(f"Identifire: {identifire.get('schemeID')} @ {identifire.text}")
    return identifire.get("schemeID"), identifire.text


async def to_logger(payload: dict):
    """
    Асинхронно відправляє дані до журналу. Помилки логуються, але не передаються далі.
    """
    _logger.debug("Запускаємо процес обміну з журналом...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/logs/request", headers=HEADERS, json=payload
            )
            response.raise_for_status()
            _logger.debug("Дані успішно відправлено до журналу")
        except httpx.TimeoutException:
            _logger.exception("Тайм-аут при відправці до журналу")
        except httpx.HTTPError:
            _logger.exception("HTTP помилка при відправці до журналу")
        except Exception:
            _logger.exception("Невідома помилка при відправці до журналу")


async def to_request(as4: dict, edm: Parsing):
    edm_dict = edm.serialize()
    # STEP 1: first EDM Request

    await asyncio.sleep(0)

    requester = edm_dict.get('doc', {}).get("EvidenceRequester")
    requester_scheme, requester_id = agent_identifire(requester[0])  # type: ignore

    provider = edm_dict.get('doc', {}).get("EvidenceProvider")
    provider_scheme, provider_id = agent_identifire(provider)  # type: ignore

    person = Person()
    person.xml = edm_dict.get('query', {}).get("NaturalPerson")

    _logger.debug("Ствоюємо запит для додавання до журналу")
    payload = {
        "conversation_id": as4["conversationId"],
        "message_id": as4["messageId"],
    }
    payload.update(
        {
            "query_request_id": edm.doc.get('id'),
            "requester_id": requester_id,
            "requester_scheme": requester_scheme,
            "provider_id": provider_id,
            "provider_scheme": provider_scheme,
        }
    )
    payload["person"] = person.dict
    payload.update(
        {
            "mime_type": "application/x-ebrs+xml",
            "mime_content": etree.tostring(edm.doc).decode(),
        }
    )

    _logger.debug(f"Запит створено: {payload}")
    _logger.debug("Створюємо таску для запису в журнал")

    def _handle_logger_error(task: asyncio.Task):
        """Обробляє помилки з фонової таски логування (якщо вони якимось чином пройшли крізь try-except)"""
        try:
            task.result()
        except Exception:
            _logger.exception("Критична помилка в таски логування")

    log_task = asyncio.create_task(to_logger(payload))
    log_task.add_done_callback(_handle_logger_error)
    _logger.debug(f"Таска логування створена: {log_task.get_name()}")


async def check_servis():
    _logger.debug("Проверяем доступность сервиса журнала...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{BASE_URL}/health", headers=HEADERS)  # type: ignore
            _logger.info(f"Сервіс журналу доступний: {r.status_code}, {r.text}")
            return r.status_code == 200
        except (httpx.TimeoutException, httpx.HTTPError):
            _logger.exception("Помилка при перевірці доступності сервісу журналу")
            return False


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
