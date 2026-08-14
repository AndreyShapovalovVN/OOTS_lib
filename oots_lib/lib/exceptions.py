from lxml import etree

from oots_lib.lib.NS import NS


class EDMException(NS, Exception):
    """
    Клас користувацького виключення, який формує XML Element для EDM-помилок.
    """
    DEFAULT_MESSAGE: str | None = None
    DEFAULT_CODE: str | None = None
    DEFAULT_ETYPE: str | None = None
    DEFAULT_SEVERITY = "urn:oasis:names:tc:ebxml-regrep:ErrorSeverityType:Error"

    def __init__(
            self,
            message: str | None = None,
            code: str | None = None,
            etype: str | None = None,
            detail: str | None = None,
            severity: str | None = None,
    ):
        self.message = message or self.DEFAULT_MESSAGE
        self.code = code or self.DEFAULT_CODE
        self.e_type = etype or self.DEFAULT_ETYPE
        self.detail = detail
        self.severity = severity or self.DEFAULT_SEVERITY

        self._xml: etree._Element | None = None  # <-- інстансове, не класове

        text = self._format_text()
        Exception.__init__(self, text)

    def _format_text(self) -> str:
        parts = []
        if self.code:
            parts.append(f"[{self.code}]")
        if self.message:
            parts.append(self.message)
        if self.detail:
            parts.append(f": {self.detail}")
        return " ".join(parts) if parts else "EDMException"

    @property
    def xml(self) -> etree._Element:  # type: ignore[override]
        if self._xml is None:
            self._xml = self._element(
                "rs",
                "Exception",
                attrib={
                    self._tname("xsi", "type"): self.e_type,
                    "severity": self.severity,
                    "message": self.message,
                    "detail": self.detail,
                    "code": self.code,
                },
            )
        return self._xml

    def to_pretty_xml(self) -> str:
        return etree.tostring(self.xml, pretty_print=True, encoding="unicode")


class TypedEDMException(EDMException):
    """Базовий клас для помилок з наперед визначеними кодом, типом і текстом.

    Підклас лише оголошує `DEFAULT_*`-константи, конструктор спільний.
    """

    def __init__(self, detail: str | None = None, message: str | None = None):
        super().__init__(message=message, detail=detail)


class AuthenticationException(TypedEDMException):
    DEFAULT_MESSAGE = "Failed Authentication"
    DEFAULT_CODE = "EDM:ERR:0001"
    DEFAULT_ETYPE = "rs:AuthenticationExceptionType"
    DEFAULT_SEVERITY = "urn:sr.oots.tech.ec.europa.eu:codes:ErrorSeverity:EDMErrorResponse:PreviewRequired"


class AuthorizationException(TypedEDMException):
    DEFAULT_MESSAGE = "Failed Authentication"
    DEFAULT_CODE = "EDM:ERR:0002"
    DEFAULT_ETYPE = "rs:AuthorizationExceptionType"
    DEFAULT_SEVERITY = "urn:sr.oots.tech.ec.europa.eu:codes:ErrorSeverity:EDMErrorResponse:PreviewRequired"


class InvalidRequestException(TypedEDMException):
    DEFAULT_MESSAGE = "Syntactically or semantically invalid request"
    DEFAULT_CODE = "EDM:ERR:0003"
    DEFAULT_ETYPE = "rs:InvalidRequestExceptionType"


class ObjectNotFoundException(TypedEDMException):
    DEFAULT_MESSAGE = "Object not found"
    DEFAULT_CODE = "EDM:ERR:0004"
    DEFAULT_ETYPE = "rs:ObjectNotFoundExceptionType"


class TimeoutException(TypedEDMException):
    DEFAULT_MESSAGE = "Exceeding a timeout period"
    DEFAULT_CODE = "EDM:ERR:0005"
    DEFAULT_ETYPE = "rs:TimeoutExceptionType"


class UnresolvedReferenceException(TypedEDMException):
    DEFAULT_MESSAGE = "Referenced object that cannot be resolved"
    DEFAULT_CODE = "EDM:ERR:0006"
    DEFAULT_ETYPE = "rs:UnresolvedReferenceExceptionType"


class UnsupportedCapabilityException(TypedEDMException):
    DEFAULT_MESSAGE = "Optional features or capabilities are not supported"
    DEFAULT_CODE = 'EDM:ERR:0007'
    DEFAULT_ETYPE = "rs:UnsupportedCapabilityExceptionType"


class QueryException(TypedEDMException):
    DEFAULT_MESSAGE = "Query Exception"
    DEFAULT_CODE = "EDM:ERR:0008"
    DEFAULT_ETYPE = "query:QueryExceptionType"


__all__ = [
    "AuthenticationException",
    "AuthorizationException",
    "EDMException",
    "InvalidRequestException",
    "ObjectNotFoundException",
    "QueryException",
    "TimeoutException",
    "TypedEDMException",
    "UnresolvedReferenceException",
    "UnsupportedCapabilityException",
]
