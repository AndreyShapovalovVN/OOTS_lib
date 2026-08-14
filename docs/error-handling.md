# Обробка помилок

Головний принцип бібліотеки: **помилка не зникає без слідів**. Кожна невдала операція
або кидає виключення, або залишає стан, який викликач може перевірити. Причина
оригінальної помилки завжди зберігається через `raise ... from e`.

## Типи виключень

| Виключення | Модуль | Коли виникає |
| --- | --- | --- |
| `EDMException` | `oots_lib.libs.exception` | Помилка обробки повідомлення EDM. Додатково публікується до Redis і черги |
| `TransportError` | `oots_lib.libs.exception` | Помилка обміну з сервісом даних, коли `SOAPTransport(if_send_error=False)` |
| `ReportingError` | `oots_lib.libs.exception` | Не вдалося опублікувати `EDMException` до Redis або черги |
| `RedisDataError` | `oots_lib.libs.UseRedis` | Значення у Redis не є валідним JSON |
| `KeyIsNone` | `oots_lib.libs.UseRedis` | Ключ Redis передано як `None` |
| `LoggerServiceError` | `oots_lib.libs.toLogger` | Сервіс журналювання недоступний або повернув HTTP-помилку |
| `BaseEDMException` та похідні | `oots_lib.libs.exceptions` | Помилки OOTS для віддачі у SOAP-відповіді у форматі XML |

## EDMException: публікація помилки

`EDMException` — не просто виключення, а й спосіб доставити помилку до споживача:
дані помилки зберігаються у Redis за ключем `oots:message:response:exp:{message_id}`,
а `message_id` кладеться до черги `QUEUE_OUTCOMING`.

```python
raise EDMException(
    redis=redis,
    queue=None,             # None → QUEUE_OUTCOMING
    key=None,               # None → KEYS.get_response_exp(message_id)
    message_id=message_id,
    code="EDM:ERR:0004",
    message="Інформацію про людину не знайдено",
    detail=f"У Redis відсутні дані особи за ключем {person_key}",
)
```

Публікація стартує автоматично у конструкторі:

- у **асинхронному** контексті створюється задача (сильне посилання зберігається у
  модульному `_reporting_tasks`, тому GC її не прибере) і результат перевіряється у
  callback;
- у **синхронному** контексті виконується `asyncio.run(self.report())`.

Стан публікації доступний на самому виключенні:

```python
try:
    ...
except EDMException as e:
    e.reported          # bool — чи опубліковано успішно
    e.reporting_error   # BaseException | None — чому не вдалося
    e.reporting_task    # asyncio.Task | None
    await e.report()    # детермінована повторна спроба; кидає ReportingError
```

Невдала публікація **не** кидається з конструктора: інакше вона підмінила б первинну
причину помилки. Замість цього вона фіксується у `reporting_error` і журналюється як
`ERROR`. Якщо доставка помилки критична для процесу, викличте `await e.report()`
самостійно та обробіть `ReportingError`.

## Коди помилок EDM

| Код | Значення |
| --- | --- |
| `EDM:ERR:0003` | У запиті не вказано тип контенту (`sdg:DistributedAs/sdg:Format`) |
| `EDM:ERR:0004` | Не знайдено запит EDM або дані особи |
| `EDM:ERR:0006` | Помилка обміну з сервісом даних або невідомий тип контенту |

## SOAPTransport

`send_error_message()` завжди завершується виключенням (`NoReturn`), тому виконання
ніколи не продовжується з несформованим з'єднанням чи відповіддю:

```python
def send_error_message(self, code, message, detail, cause=None) -> NoReturn:
    if self.if_send_error:
        raise EDMException(...) from cause   # + публікація до Redis/черги
    raise TransportError(f"[{code}] {message}: {detail}") from cause
```

Метод викликається, якщо не створено `XClient`, якщо запит до Трембіти впав або якщо
відповідь має неочікувану структуру.

Виняток — журналювання транзакції: збій `ToLogger` не скасовує вже виконаний обмін
даними, тому він лише журналюється через `logger.exception`.

## Redis

- `get_from_redis()` повертає `None` **лише** якщо ключа немає; пошкоджений JSON кидає
  `RedisDataError`, тобто «немає даних» і «дані зіпсовані» не змішуються.
- `get_flag()` навмисно повертає значення `default` для некоректного JSON (прапор не
  повинен ламати процес), але пише про це попередження.
- `health()` повертає `bool` для health-endpoint, `health_check()` кидає
  `redis.exceptions.ConnectionError` — для ініціалізації.
- `disconnect()` — best-effort: помилка закриття журналюється як попередження, бо на
  цьому етапі процес уже завершується.

## Сервіс журналювання

`ToLogger.send_to_logger()` кидає `LoggerServiceError` і для мережевих помилок
(`httpx.HTTPError`), і для відповіді зі статусом помилки. Тексти помилок не містять
API-ключа.

## Змінні оточення

`import_env()` кидає `ValueError` для відсутньої обов'язкової змінної під час імпорту
модуля — конфігураційна проблема виявляється на старті, а не під час обробки першого
повідомлення.
