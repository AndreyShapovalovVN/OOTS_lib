# `toLogger` — інструкція використання

Модуль `oots_lib.lib.toLogger` відповідає за журналювання подій обміну до сервісу
Traceability Logger.

У модулі більше **немає легасі-обгорток** (`ToLogger`, `to_logger`, `to_request` тощо).
Використовуйте тільки `TraceabilityLogger` + функції побудови payload.

## Залежності та конфігурація

Потрібні змінні оточення:

- `EXCHANGE_LOGGER_URI` — базовий URL сервісу.
- `EXCHANGE_LOGGER_API_KEY` — API-ключ.

За відсутності будь-якої з цих змінних `TraceabilityLogger(...)` кидає `ValueError`.

## Імпорт

```python
from oots_lib.lib.toLogger import (
    TraceabilityLogger,
    build_request_payload,
    build_response_payload,
    build_trembita_payload,
)
```

## 1) Логування Evidence Request (async)

```python
from pyRegRep4.RIMParsing import Parsing

as4 = {
    "conversationId": "conv-123",
    "messageId": "msg-123",
}
edm = Parsing(raw_edm_xml_bytes)

payload = build_request_payload(as4, edm)

logger = TraceabilityLogger()
ok = await logger.log_request(payload)
```

`ok == True` означає успішний HTTP-виклик (2xx).

## 2) Логування Evidence Response (async)

```python
as4 = {
    "conversationId": "conv-123",
    "messageId": "msg-124",
}

payload = build_response_payload(as4, edm_response_xml_bytes_or_str)

logger = TraceabilityLogger()
ok = await logger.log_response(payload)
```

## 3) Логування Trembita-транзакції

### Async-варіант

```python
payload = build_trembita_payload("conv-123")
payload["calls"].append({
    "dataservice": "GetDocumentsByPerson",
    "timestamp": "2026-10-08T14:00:00",
    "trembita_msg_id": "uuid-1",
    "transaction_id": "tx-1",
})

logger = TraceabilityLogger()
ok = await logger.log_trembita(payload)
```

### Sync-варіант (для синхронних кодшляхів)

```python
payload = build_trembita_payload("conv-123")
payload["calls"].append({...})

logger = TraceabilityLogger(raise_on_error=True)
ok = logger.log_trembita_sync(payload)
```

Якщо `raise_on_error=True`, при HTTP/мережевій помилці буде `LoggerServiceError`.

## 4) Background-логування (fire-and-forget)

```python
payload = build_request_payload(as4, edm)
logger = TraceabilityLogger()

task = logger.log_in_background("request", payload, check_health=True)
# Не await-те task, якщо потрібен саме fire-and-forget режим.
```

- Якщо `check_health=True`, перед відправкою виконується `GET /health`.
- При недоступності сервісу запис пропускається, повертається `False`.
- Невиловлені помилки всередині task логуються через module logger.

## 5) Повторне використання HTTP-пулу

Якщо відправляєте багато записів підряд, використовуйте контекстний менеджер:

```python
async with TraceabilityLogger() as logger:
    await logger.log_request(request_payload)
    await logger.log_response(response_payload)
    await logger.log_trembita(trembita_payload)
```

Це зменшує накладні витрати на створення HTTP-зʼєднань.

## Поведінка при не-JSON значеннях у payload

Перед відправкою модуль нормалізує payload до JSON-безпечного вигляду:

- `bytes` → UTF-8 string (`errors="replace"`),
- `lxml.etree._Element` → XML string,
- `Mapping` / `list` / `tuple` / `set` → рекурсивно,
- інші обʼєкти → `str(value)`.

Це запобігає помилкам виду:
`TypeError: Object of type ... is not JSON serializable`.

## Мінімальна схема вибору методу

- Є AS4 + EDM запит → `build_request_payload` + `log_request`.
- Є AS4 + EDM відповідь → `build_response_payload` + `log_response`.
- Лог транспортного виклику Трембіти → `build_trembita_payload` + `log_trembita` / `log_trembita_sync`.
