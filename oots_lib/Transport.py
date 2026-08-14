import logging
from abc import ABC, abstractmethod
from typing import NoReturn

from XRoad import RedisCache, Transport, XClient
from XRoad.plugins import UXPHistoryPlugin

from oots_lib.import_env import import_env
from oots_lib.libs.exception import EDMException, TransportError
from oots_lib.libs.toLogger import ToLogger
from oots_lib.libs.UseRedis import get_redis_client

_logger = logging.getLogger(__name__)

TREMBITA_URL = import_env("TREMBITA_URL")
TREMBITA_CLIENT_ID = import_env("TREMBITA_CLIENT_ID")
TREMBITA_CACHE = int(import_env("TREMBITA_CACHE"))
REDIS_URL = import_env("REDIS_URL")


class SOAPTransport(ABC):
    def __init__(self, service: str, conversation_id: str, if_send_error: bool = True):
        self.service = service
        self.conversation_id = conversation_id
        self.if_send_error = if_send_error

        self.to_logger = ToLogger(conversation_id)
        self.redis = get_redis_client()

        _logger.info(f"Надсилаємо запит до сервісу: {self.service}")

        cache = RedisCache(REDIS_URL, timeout=3600 * 24)
        transport = Transport(operation_timeout=60 * 5, cache=cache)
        self.history = UXPHistoryPlugin()

        self.client = None
        try:
            self.client = XClient(
                TREMBITA_URL, client=TREMBITA_CLIENT_ID, service=self.service,
                transport=transport,
                plugins=[self.history, ]
            )
        except Exception as e:
            _logger.exception("Помилка створення XClient")
            self.send_error_message(
                code="EDM:ERR:0006",  # NOSONAR
                message="Сталася помилка при створенні з'єднення до Трембіти",
                detail=f"Сталася помилка при створенні з'єднення до Трембіти: {e}",
                cause=e,
            )

        _logger.info(f"XClient успішно створений: {self.client}")

    def send_error_message(
        self,
        code: str,
        message: str,
        detail: str,
        cause: BaseException | None = None,
    ) -> NoReturn:
        """Сигналізує про помилку транспорту виключенням.

        При `if_send_error` помилка додатково публікується до Redis та черги
        через :class:`EDMException`, інакше кидається :class:`TransportError`.
        Метод завжди кидає виключення, щоб помилка не залишалась непоміченою.
        """
        _logger.error(f"Помилка: code={code}, message={message}, detail={detail}")
        if self.if_send_error:
            raise EDMException(
                redis=self.redis,
                queue=None,
                key=None,
                message_id=str(self.conversation_id),
                code=code,
                message=message,
                detail=detail,
            ) from cause

        raise TransportError(f"[{code}] {message}: {detail}") from cause

    @abstractmethod
    def parsing_response(self, responce: dict) -> list[dict]:
        ...

    def response(self, request: dict) -> list[dict]:

        _logger.info(f"Запит до сервісу: {self.service}")
        if self.client is None:
            self.send_error_message(
                code="EDM:ERR:0006",
                message="З'єднання до Трембіти не встановлено",
                detail=f"XClient для сервісу {self.service} не створений",
            )

        try:
            response = self.client.request(**request)
        except Exception as e:
            _logger.exception("Помилка виконання запиту до Трембіти")
            self.send_error_message(
                code="EDM:ERR:0006",
                message="Сталася помилка при виконанні запиту до Сервісу даних",
                detail=f"Сталася помилка при виконанні запиту до Сервісу даних: {e}",
                cause=e,
            )

        try:
            result = response["body"]
        except (KeyError, IndexError, TypeError) as e:
            self.send_error_message(
                code="EDM:ERR:0006",
                message="Відповідь від Сервісу даних має некоректну структуру",
                detail=f"Не вдалося отримати body.GetDocumentsByPersonResult: {e}",
                cause=e,
            )

        self._logging_trembita_transaction()

        _logger.debug(f"Результат відповіді: {result}")
        return self.parsing_response(result)

    def _logging_trembita_transaction(self):
        if self.to_logger is None or self.client is None or self.history is None:
            _logger.debug("Журналювання транзакції пропущено: відсутні client/history або логер")
            return

        self.to_logger.append_calls(
            {
                "dataservice": self.service,
                "timestamp": self.history.transaction_date.isoformat(),
                "trembita_msg_id": self.client.id,
                "transaction_id": self.history.transaction_id,
            }
        )

        _logger.debug(f"Дані журналу транзакції: {self.to_logger.payload}")
        try:
            self.to_logger.send_to_logger()
        except Exception:
            _logger.exception("Не вдалося надіслати журнал транзакції")
