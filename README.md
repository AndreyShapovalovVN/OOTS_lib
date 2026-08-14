# OOTS_lib

Python-бібліотека для обміну доказами (evidences) у межах **OOTS** (Once-Only Technical
System) через українську платформу взаємодії **Трембіта** (X-Road).

Бібліотека покриває три задачі:

1. **Моделі даних** — `EDMRequest`, `Person`, `Evidences` та RegRep4-обгортки
   (`RegistryPackageType`, `ExtrinsicObjectType`) із серіалізацією у XML/JSON/PDF.
2. **Транспорт** — `SOAPTransport` для викликів сервісів даних через Трембіту.
3. **Оркестрація стану** — читання запиту та даних особи з Redis, формування набору
   доказів (`MakeEvidence`) і публікація результату до черги обробки.

- [Публічний API](docs/api.md)
- [Модель обробки помилок](docs/error-handling.md)

## Встановлення

```bash
pip install oots-lib            # рантайм
pip install "oots-lib[pdf]"     # + генерація PDF (WeasyPrint)
pip install "oots-lib[dev]"     # + ruff, mypy, pytest
```

Потрібен Python 3.12+ та доступний Redis.

## Змінні оточення

Усі змінні читаються під час **імпорту** модулів через `import_env()`: якщо обов'язкової
змінної немає, імпорт падає з `ValueError`. Задавайте їх до старту застосунку.

| Змінна | Обов'язкова | Опис |
| --- | --- | --- |
| `TREMBITA_URL` | так | URL сервера безпеки Трембіти |
| `TREMBITA_CLIENT_ID` | так | Ідентифікатор клієнта X-Road |
| `TREMBITA_CACHE` | так | TTL кешу WSDL, секунди |
| `REDIS_URL` | так | DSN Redis, напр. `redis://localhost:6379/0` |
| `REDIS_TTL` | так | TTL значень, які пише бібліотека, секунди |
| `REDIS_PREFIX` | ні (`""`) | Префікс ключів і черг |
| `REDIS_TIMEOUT` | ні (`6`) | Таймаут `BRPOP`, секунди |
| `QUEUE_OUTCOMING` | так | Черга, до якої публікуються готові повідомлення та помилки |
| `IF_PREVIEW` | так | `true` — примусово вимагати preview перед відправкою |
| `COUNTRY` | так | Код країни для ідентифікаторів особи |
| `EXCHANGE_LOGGER_URI` | так | Базовий URL сервісу журналювання транзакцій |
| `EXCHANGE_LOGGER_API_KEY` | так | API-ключ сервісу журналювання |

`EXCHANGE_LOGGER_URI` без `https://` призводить до попередження у журналі: API-ключ
передавався б у відкритому вигляді.

## Швидкий старт

### Redis

```python
from oots_lib import initialize_redis, close_redis, get_redis_client

await initialize_redis()          # створює та перевіряє глобальне з'єднання
redis = get_redis_client()        # singleton, той самий екземпляр усюди
...
await close_redis()
```

### Формування доказів

`MakeEvidence` — базовий клас для успадкування: задайте реквізити органу, що видає
доказ, і джерело даних (`self.data` — модель, похідна від `MainBase`).

```python
from oots_lib import MakeEvidence, get_redis_client

class MarriageEvidence(MakeEvidence):
    ISSUING_AUTHORITY_ID = "UA:MIN:JUSTICE"
    ISSUING_AUTHORITY_SCHEME = "UA"
    ISSUING_AUTHORITY_NAME = "Міністерство юстиції України"
    CONFORMANT_TO_URL = "https://sr.oots.tech.ec.europa.eu/..."

evidence = MarriageEvidence(message_id, get_redis_client())
await evidence.read_data()        # запит EDM + дані особи з Redis
evidence.data = MarriageRecord()  # джерело документів (MainBase)
await evidence.transform_data()   # PDF / XML / JSON згідно sdg:Format запиту
await evidence.load_data_to_redis()
```

`load_data_to_redis()` зберігає `Evidences` за ключем
`oots:message:response:evidence:{message_id}` і, якщо preview не потрібен, кладе
`message_id` до `QUEUE_OUTCOMING`.

### Виклик сервісу даних

```python
from oots_lib import SOAPTransport

class DocumentsService(SOAPTransport):
    def parsing_response(self, responce: dict) -> list[dict]:
        return responce["GetDocumentsByPersonResult"]["documents"]

service = DocumentsService("GetDocumentsByPerson", conversation_id)
documents = service.response({"person": {"rnokpp": "1234567890"}})
```

Кожна помилка транспорту завершується виключенням (див.
[обробку помилок](docs/error-handling.md)); успішний виклик додатково журналюється до
сервісу обміну через `ToLogger`.

## Схема ключів Redis

Ключі формує `oots_lib.redis_keys.Keys`, щоб схема не дублювалась у застосунках:

| Метод | Шаблон ключа |
| --- | --- |
| `get_request_edm` | `oots:message:request:edm:{conversation_id}` |
| `get_request_person` | `oots:message:request:person:{conversation_id}` |
| `get_request_as4` | `oots:message:request:as4:{conversation_id}` |
| `get_request_preview` | `oots:message:request:preview:{conversation_id}` |
| `get_response_evidence` | `oots:message:response:evidence:{conversation_id}` |
| `get_response_edm` | `oots:message:response:edm:{conversation_id}` |
| `get_response_exp` | `oots:message:response:exp:{conversation_id}` |
| `get_evidence_type` | `oots:evidencetype:{evidence_type_id}` |

`REDIS_PREFIX` додається до ключа автоматично на рівні `UseRedisAsync`.

## Структура проєкту

```
oots_lib/
├── Transport.py        SOAPTransport — виклики сервісів даних через Трембіту
├── import_env.py       читання обов'язкових змінних оточення
├── redis_keys.py       централізована схема ключів Redis
├── libs/
│   ├── MakeEvidence.py     формування набору доказів з даних у Redis
│   ├── UseRedis.py         асинхронний клієнт Redis, черги, прапори
│   ├── exception.py        EDMException + публікація помилки до Redis/черги
│   ├── exceptions.py       SOAP-помилки OOTS у вигляді XML
│   ├── EvidanceMetadata.py метадані доказу (isAbout, distribution, ...)
│   ├── CreatePDF.py        XSLT → HTML → PDF (WeasyPrint)
│   ├── xml_safety.py       безпечний парсинг XML (без DTD/entities)
│   └── NS.py               XML-простори імен
└── models/
    ├── Base.py             Base/MainBase: XML, JSON, dict, PDF
    ├── Person.py           Person, Identifier + збереження у Redis
    ├── RequestEDM.py       EDMRequest + збереження у Redis
    └── ResponseEvidences.py Evidences та RegRep4-структури
```

Публічні імена експортуються з `oots_lib` через ліниві імпорти, тому
`from oots_lib import Person` не тягне за собою `weasyprint` чи клієнт X-Road.

## Розробка

```bash
pip install -e ".[dev]"
ruff check .
mypy . --ignore-missing-imports
pytest
```

CI (`.github/workflows/ci-security-quality.yml`) додатково виконує Gitleaks (пошук
секретів) і Trivy (сканування файлової системи). Публікація до PyPI —
`.github/workflows/python-publish.yml` через Trusted Publishing (OIDC).
