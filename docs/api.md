# Публічний API

Усі імена доступні напряму з `oots_lib` (ліниві імпорти — важкі залежності
підтягуються лише при першому зверненні).

## Redis

```python
from oots_lib import UseRedisAsync, get_redis_client, initialize_redis, close_redis
```

| Функція / метод | Опис |
| --- | --- |
| `initialize_redis(redis_url=None)` | Створює глобальне з'єднання та перевіряє його (`health_check`) |
| `get_redis_client()` | Повертає глобальний `UseRedisAsync` (створює за потреби) |
| `close_redis()` | Закриває глобальне з'єднання |
| `get_from_redis(key)` | JSON → `dict`/`list`; `None` якщо ключа немає |
| `save_to_redis(key, data)` | JSON із TTL `REDIS_TTL` |
| `get_raw_from_redis` / `save_raw_to_redis` | Робота з `bytes` без серіалізації |
| `push_to_queue(queue, message)` | `LPUSH` до черги |
| `pop_from_queue(queue)` | `BRPOP` з таймаутом `REDIS_TIMEOUT`; `None` при таймауті |
| `set_flag` / `get_flag` | Булеві прапори (наприклад, підтвердження preview) |
| `delete_from_redis(key)` | Видалення ключа |
| `health()` / `health_check()` | Перевірка з'єднання: `bool` / виключення |
| `disconnect()` | Закриття з'єднання (також через `async with`) |

Ключі автоматично отримують префікс `REDIS_PREFIX`; повторне префіксування не
відбувається.

## Моделі

```python
from oots_lib import EDMRequest, Person, Identifier, Evidences
from oots_lib.models import save_person_to_redis, get_person_from_redis
```

- `EDMRequest(href, MimeType, content, process_queue=None, content2=None)` —
  вхідний запит EDM. `save_edm_request_to_redis()` / `get_edm_request_from_redis()`
  підтримують і історичний формат зберігання списком.
- `Person` — особа, про яку запитують доказ. Приймає XML (`person.xml = ...`) або
  словник (`Person.set_from_dict()`), віддає `get_xml()`, `get_dict()`, `get_json()`,
  `xml_tree`.
- `Identifier(value, schemeID="eidas")` — ідентифікатор особи; країна береться з
  `COUNTRY`.
- `Evidences(title, PreviewDescription, preview, evidences)` — набір доказів для
  відповіді, складається з `RegistryPackageType` → `ExtrinsicObjectType`.
  `to_legacy_evidences_dict()` та `get_legacy_evidences_from_redis()` конвертують до
  старого формату для сумісності.

Похідні від `MainBase` моделі документів отримують `get_xml()`, `get_dict()`,
`get_json()` і `get_pdf(xslt_file, css=None)`; підклас має реалізувати `get_element()`.

## MakeEvidence

| Член | Опис |
| --- | --- |
| `ISSUING_AUTHORITY_ID` / `_SCHEME` / `_NAME` | Реквізити органу, що видає доказ |
| `CONFORMANT_TO_URL` | URL специфікації, якій відповідає доказ |
| `await read_data()` | Читає запит EDM, дані особи та AS4-контекст з Redis |
| `self.data` | Джерело документів (`MainBase`), задається перед `transform_data()` |
| `await transform_data()` | Формує `Evidences` у форматі із `sdg:Format` (pdf/xml/json) |
| `await load_data_to_redis()` | Зберігає `Evidences` і, якщо preview не потрібен, публікує до `QUEUE_OUTCOMING` |
| `if_preview` | Чи потрібне підтвердження перед відправкою (прапор запиту або `IF_PREVIEW`) |
| `request_content_type` | `sdg:DistributedAs/sdg:Format` із запиту |
| `generate_metadata(main_evidence=True)` | XML метаданих доказу (`isAbout`, `distribution`, `issuingAuthority`) |

## SOAPTransport

```python
SOAPTransport(service: str, conversation_id: str, if_send_error: bool = True)
```

| Член | Опис |
| --- | --- |
| `parsing_response(responce)` | Абстрактний: розбір `body` відповіді сервісу |
| `response(request)` | Виконує запит, журналює транзакцію, повертає `parsing_response(...)` |
| `send_error_message(code, message, detail, cause=None)` | Завжди кидає виключення (`EDMException` або `TransportError`) |
| `if_send_error` | `True` — помилка публікується як `EDMException`; `False` — `TransportError` |

## PDF

```python
from oots_lib import generate_pdf_from_xslt

pdf: bytes = generate_pdf_from_xslt(rdf=xml_string, xslt_file=path, css=["h1 { color: navy }"])
```

Потрібен extra `pdf` (WeasyPrint); без нього виклик кидає `ModuleNotFoundError`.
Шаблони за замовчуванням (`rdf-display.xsl`, `annexI_birth.xsl`, `annexIV_marriage.xsl`,
`disability.xsl`) до пакета не входять — передавайте власний `xslt_file`. XSLT
виконується з `XSLTAccessControl.DENY_ALL`, XML парситься без DTD та зовнішніх сутностей
(`oots_lib.libs.xml_safety`).

## SOAP-помилки OOTS

`BaseEDMException` та похідні (`AuthenticationException`, `AuthorizationException`,
`InvalidRequestException`, `ObjectNotFoundException`, `QueryException`,
`TimeoutException`, `UnresolvedReferenceException`, `UnsupportedCapabilityException`)
формують XML-представлення помилки для SOAP-відповіді:

```python
from oots_lib import ObjectNotFoundException

exc = ObjectNotFoundException(detail="Особу не знайдено у реєстрі")
xml = exc.to_pretty_xml()
```
