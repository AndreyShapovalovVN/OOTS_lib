"""Client library for the OOTS Traceability Logger service.

Use :class:`TraceabilityLogger` for request/response/trembita logging and
the payload builder helpers for schema-compliant bodies.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any, Literal

import httpx
from lxml import etree
from pyRegRep4.RIMParsing import Parsing  # type: ignore[import-untyped]

from oots_lib.import_env import import_env
from oots_lib.models.Person import Person

_logger = logging.getLogger(__name__)

LogKind = Literal["request", "trembita", "response"]


class LoggerServiceError(RuntimeError):
    """The traceability logger could not accept a log record."""


class TraceabilityLogger:
    """Single asynchronous client for all Traceability Logger endpoints.

    The client does not own application payload construction: payloads follow
    the schemas from the service's OpenAPI contract.  Reuse the instance with
    ``async with`` to reuse its HTTP connection pool.
    """

    def __init__(
            self,
            base_url: str | None = None,
            api_key: str | None = None,
            *,
            timeout: float = 30.0,
            raise_on_error: bool = False,
    ) -> None:
        self.base_url = (base_url or import_env("EXCHANGE_LOGGER_URI", "")).rstrip("/")
        self.api_key = api_key or import_env("EXCHANGE_LOGGER_API_KEY", "")
        self.timeout = timeout
        self.raise_on_error = raise_on_error
        self._client: httpx.AsyncClient | None = None

        if not self.base_url:
            raise ValueError("EXCHANGE_LOGGER_URI is not configured")
        if not self.api_key:
            raise ValueError("EXCHANGE_LOGGER_API_KEY is not configured")
        if not self.base_url.startswith("https://"):
            _logger.warning(
                "EXCHANGE_LOGGER_URI does not use HTTPS; the API key is sent unencrypted"
            )

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    async def __aenter__(self) -> TraceabilityLogger:
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health(self) -> bool:
        """Return whether the logger and its database are available."""
        response = await self._request("GET", "/health")
        return response is not None and response.status_code == httpx.codes.OK

    async def log_request(self, payload: Mapping[str, Any]) -> bool:
        response = await self._request("POST", "/logs/request", json=dict(payload))
        return response is not None and response.is_success

    async def log_trembita(self, payload: Mapping[str, Any]) -> bool:
        response = await self._request("POST", "/logs/trembita", json=dict(payload))
        return response is not None and response.is_success

    async def log_response(self, payload: Mapping[str, Any]) -> bool:
        response = await self._request("POST", "/logs/response", json=dict(payload))
        return response is not None and response.is_success

    def log_trembita_sync(self, payload: Mapping[str, Any]) -> bool:
        """Synchronous Trembita logging for call sites without an event loop."""
        response = self._request_sync("POST", "/logs/trembita", json=dict(payload))
        return response is not None and response.is_success

    def log_in_background(
            self,
            kind: LogKind,
            payload: Mapping[str, Any],
            *,
            check_health: bool = True,
    ) -> asyncio.Task[bool]:
        """Schedule non-blocking logging and return the created task.

        When ``check_health`` is enabled, the background task calls ``/health``
        first and skips sending the record when the logger is unavailable.
        The caller must not await the returned task when fire-and-forget
        behaviour is desired.
        """
        task = asyncio.create_task(
            self._log_in_background(kind, dict(payload), check_health=check_health)
        )
        task.add_done_callback(_report_background_failure)
        return task

    async def _log_in_background(
            self,
            kind: LogKind,
            payload: Mapping[str, Any],
            *,
            check_health: bool,
    ) -> bool:
        if check_health and not await self.health():
            _logger.warning("Traceability Logger is unavailable; %s log was skipped", kind)
            return False
        response = await self._request("POST", f"/logs/{kind}", json=dict(payload))
        return response is not None and response.is_success

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        if "json" in kwargs:
            kwargs["json"] = _make_json_safe(kwargs["json"])
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
        )
        try:
            response = await client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            _logger.debug("Traceability Logger %s %s: %s", method, path, response.status_code)
            return response
        except httpx.HTTPError as exc:
            error = LoggerServiceError(f"Traceability Logger {method} {path} failed: {exc}")
            if self.raise_on_error:
                raise error from exc
            _logger.warning("%s", error)
            return None
        finally:
            if owns_client:
                await client.aclose()

    def _request_sync(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        if "json" in kwargs:
            kwargs["json"] = _make_json_safe(kwargs["json"])
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            _logger.debug("Traceability Logger %s %s: %s", method, path, response.status_code)
            return response
        except httpx.HTTPError as exc:
            error = LoggerServiceError(f"Traceability Logger {method} {path} failed: {exc}")
            if self.raise_on_error:
                raise error from exc
            _logger.warning("%s", error)
            return None


def _make_json_safe(value: Any) -> Any:
    """Convert values to JSON-serializable structures for logging payloads."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, etree._Element):
        return etree.tostring(value, encoding="unicode")
    if isinstance(value, Mapping):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(item) for item in value]
    return str(value)


def agent_identifier(agent: etree._Element | None) -> tuple[str | None, str | None]:
    """Extract ``(schemeID, value)`` from an OOTS Agent element."""
    if agent is None:
        return None, None
    identifier = agent.find(".//sdg:Identifier", namespaces=agent.nsmap)
    if identifier is None:
        return None, None
    return identifier.get("schemeID"), identifier.text


def build_request_payload(as4: Mapping[str, Any], edm: Parsing) -> dict[str, Any]:
    """Build an ``EvidenceRequestCreate`` payload from parsed AS4/EDM data."""
    edm_dict = edm.serialize()
    doc = edm_dict.get("doc", {})

    requester = doc.get("EvidenceRequester")
    requester_element = requester[0] if isinstance(requester, list) and requester else requester
    requester_scheme, requester_id = agent_identifier(requester_element)

    provider = doc.get("EvidenceProvider")
    provider_element = provider[0] if isinstance(provider, list) and provider else provider
    provider_scheme, provider_id = agent_identifier(provider_element)

    person = Person()
    person.xml = edm_dict.get("query", {}).get("NaturalPerson")

    return {
        "conversation_id": as4["conversationId"],
        "message_id": as4["messageId"],
        "query_request_id": edm.doc.get("id"),
        "requester_id": requester_id,
        "requester_scheme": requester_scheme,
        "provider_id": provider_id,
        "provider_scheme": provider_scheme,
        "person": person.dict,
        "mime_type": "application/x-ebrs+xml",
        "mime_content": etree.tostring(edm.doc, encoding="unicode"),
    }


def build_trembita_payload(conversation_id: str) -> dict[str, Any]:
    """Build a ``TrembitaLogCreate`` payload with an empty calls list."""
    return {"conversation_id": conversation_id, "calls": []}


def build_response_payload(
        as4: Mapping[str, Any],
        edm: bytes | str,
) -> dict[str, Any]:
    """Build an ``EvidenceResponseCreate`` payload from AS4/EDM data."""
    raw_edm = edm if isinstance(edm, bytes) else edm.encode("utf-8")
    mime_content = edm.decode("utf-8", errors="replace") if isinstance(edm, bytes) else edm
    parsed = Parsing(raw_edm)
    serialized = parsed.serialize()
    doc = serialized.get("doc", {})
    exception = serialized.get("exception", {})

    provider = doc.get("ErrorProvider") or doc.get("EvidenceProvider")
    provider_element = provider[0] if isinstance(provider, list) and provider else provider
    provider_scheme, provider_id = agent_identifier(provider_element)

    requester = doc.get("EvidenceRequester")
    requester_element = requester[0] if isinstance(requester, list) and requester else requester
    requester_scheme, requester_id = agent_identifier(requester_element)

    return {
        "conversation_id": as4["conversationId"],
        "message_id": as4.get("messageId", ""),
        "request_id": parsed.doc.get("requestId"),
        "requester_id": requester_id,
        "requester_scheme": requester_scheme,
        "provider_id": provider_id,
        "provider_scheme": provider_scheme,
        "response_identifier_slot": doc.get("EvidenceResponseIdentifier"),
        "preview_location": exception.get("PreviewLocation"),
        "person": None,
        "mime_type": "application/x-ebrs+xml",
        "mime_content": mime_content,
        "evidense_items": [],  # Field name is intentionally kept as defined by the API.
    }


def _report_background_failure(task: asyncio.Task[Any]) -> None:
    """Consume and report an exception raised by a fire-and-forget task."""
    try:
        task.result()
    except asyncio.CancelledError:
        _logger.debug("Background Traceability Logger task was cancelled")
    except Exception:
        _logger.exception("Background Traceability Logger task failed")
