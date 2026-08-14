import asyncio
import logging
import os

from oots_lib.libs.UseRedis import UseRedisAsync
from oots_lib.redis_keys import Keys

_logger = logging.getLogger(__name__)

KEYS = Keys()

# Сильні посилання на фонові задачі публікації помилок, щоб їх не прибрав GC.
_reporting_tasks: set[asyncio.Task] = set()


class TransportError(Exception):
    """Помилка обміну з сервісом даних, яку не публікують як EDM-помилку."""


class ReportingError(RuntimeError):
    """Не вдалося опублікувати EDM-помилку до Redis або черги."""


class EDMException(Exception):
    QUEUE_OUTCOMING = os.getenv("QUEUE_OUTCOMING")

    def __init__(
        self,
        redis: UseRedisAsync,
        queue: str | None,
        key: str | None,
        message_id: str,
        code: str,
        message: str,
        detail: str,
        preview_link: str | None = None,
    ):
        self.code = code
        self.message = message
        self.detail = detail
        self.redis = redis
        self.queue = queue or self.QUEUE_OUTCOMING
        self.key = key or KEYS.get_response_exp(message_id)
        self.message_id = message_id
        self.preview_link = preview_link

        # Стан публікації помилки: доступний викликачу для перевірки.
        self.reported = False
        self.reporting_error: BaseException | None = None
        self.reporting_task: asyncio.Task | None = None

        super().__init__(f"[{self.code}] {self.message}: {detail}")

        self._on_exception_created()

    def _on_exception_created(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                asyncio.run(self.report())
            except Exception as e:
                # Виключення не можна кидати з конструктора помилки: інакше воно
                # підмінить первинну причину. Тому лишень фіксуємо та логуємо.
                self.reporting_error = e
                _logger.exception(f"Не вдалося опублікувати помилку {self.code}")
            return

        task = loop.create_task(self.report())
        self.reporting_task = task
        _reporting_tasks.add(task)
        task.add_done_callback(self._on_reporting_done)

    def _on_reporting_done(self, task: asyncio.Task) -> None:
        _reporting_tasks.discard(task)
        if task.cancelled():
            self.reporting_error = asyncio.CancelledError()
            _logger.error(f"Публікацію помилки {self.code} скасовано")
            return

        exc = task.exception()
        if exc is not None:
            self.reporting_error = exc
            _logger.error(
                f"Не вдалося опублікувати помилку {self.code}: {exc}",
                exc_info=exc,
            )

    async def report(self) -> None:
        """Публікує помилку до Redis та черги обробки.

        Викликається автоматично при створенні виключення. Можна викликати
        (await) явно, якщо потрібна детермінована публікація або обробка
        :class:`ReportingError`.

        Raises:
            ReportingError: Якщо збереження до Redis або запис у чергу не вдались
        """
        if self.reported:
            return

        await self._save_exception_data()
        await self._push_to_queue()
        self.reported = True
        self.reporting_error = None

    async def _save_exception_data(self) -> None:
        exception_data = {
            "exception": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
                "preview_link": self.preview_link,
            }
        }
        try:
            await self.redis.save_to_redis(self.key, exception_data)
        except Exception as e:
            raise ReportingError(
                f"Не вдалося зберегти дані помилки {self.code} до Redis за ключем {self.key}: {e}"
            ) from e
        _logger.info(f"Exception data saved to Redis with key: {self.key}")

    async def _push_to_queue(self) -> None:
        if self.queue is None:
            raise ReportingError(
                "Чергу для публікації помилки не визначено: передайте queue "
                "або задайте змінну оточення QUEUE_OUTCOMING"
            )
        try:
            await self.redis.push_to_queue(self.queue, self.message_id)
        except Exception as e:
            raise ReportingError(
                f"Не вдалося покласти message_id {self.message_id} до черги {self.queue}: {e}"
            ) from e
        _logger.info(f"Message ID {self.message_id} pushed to queue: {self.queue}")
