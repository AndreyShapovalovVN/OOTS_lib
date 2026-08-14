from typing import Optional

from lxml import etree

from oots_lib.libs.NS import NS


class EDMException(NS, Exception):
    """
    Клас користувацького виключення, який формує XML Element для EDM-помилок.
    """
    DEFAULT_SEVERITY = "urn:oasis:names:tc:ebxml-regrep:ErrorSeverityType:Error"

    def __init__(
            self,
            message: Optional[str] = None,
            code: Optional[str] = None,
            etype: Optional[str] = None,
            detail: Optional[str] = None,
            severity: Optional[str] = None,
    ):
        self.message = message
        self.code = code
        self.e_type = etype
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
            attrib = self._clean_attrib({
                self._tname("xsi", "type"): self.e_type,
                "severity": self.severity,
                "message": self.message,
                "detail": self.detail,
                "code": self.code,
            })

            self._xml = etree.Element(
                self._tname("rs", "Exception"),
                nsmap=self._ns,
                attrib=attrib,
            )
        return self._xml

    @staticmethod
    def _clean_attrib(d: dict) -> dict:
        """Викидає None і приводить значення до str."""
        out = {}
        for k, v in d.items():
            if v is None:
                continue
            out[k] = str(v)
        return out

    def to_pretty_xml(self) -> str:
        return etree.tostring(self.xml, pretty_print=True, encoding="unicode")


class AuthenticationException(EDMException):
    DEFAULT_MESSAGE = "Failed Authentication"
    DEFAULT_CODE = "EDM:ERR:0001"
    DEFAULT_ETYPE = "rs:AuthenticationExceptionType"
    DEFAULT_SEVERITY = "urn:sr.oots.tech.ec.europa.eu:codes:ErrorSeverity:EDMErrorResponse:PreviewRequired"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class AuthorizationException(EDMException):
    DEFAULT_MESSAGE = "Failed Authentication"
    DEFAULT_CODE = "EDM:ERR:0002"
    DEFAULT_ETYPE = "rs:AuthorizationExceptionType"
    DEFAULT_SEVERITY = "urn:sr.oots.tech.ec.europa.eu:codes:ErrorSeverity:EDMErrorResponse:PreviewRequired"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class InvalidRequestException(EDMException):
    DEFAULT_MESSAGE = "Syntactically or semantically invalid request"
    DEFAULT_CODE = "EDM:ERR:0003"
    DEFAULT_ETYPE = "rs:InvalidRequestExceptionType"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class ObjectNotFoundException(EDMException):
    DEFAULT_MESSAGE = "Object not found"
    DEFAULT_CODE = "EDM:ERR:0004"
    DEFAULT_ETYPE = "rs:ObjectNotFoundExceptionType"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class TimeoutException(EDMException):
    DEFAULT_MESSAGE = "Exceeding a timeout period"
    DEFAULT_CODE = "EDM:ERR:0005"
    DEFAULT_ETYPE = "rs:TimeoutExceptionType"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class UnresolvedReferenceException(EDMException):
    DEFAULT_MESSAGE = "Referenced object that cannot be resolved"
    DEFAULT_CODE = "EDM:ERR:0006"
    DEFAULT_ETYPE = "rs:UnresolvedReferenceExceptionType"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class UnsupportedCapabilityException(EDMException):
    DEFAULT_MESSAGE = "Optional features or capabilities are not supported"
    DEFAULT_CODE = 'EDM:ERR:0007'
    DEFAULT_ETYPE = "rs:UnsupportedCapabilityExceptionType"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )


class QueryException(EDMException):
    DEFAULT_MESSAGE = "Query Exception"
    DEFAULT_CODE = "EDM:ERR:0008"
    DEFAULT_ETYPE = "query:QueryExceptionType"

    def __init__(self, detail: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message=message or self.DEFAULT_MESSAGE,
            code=self.DEFAULT_CODE,
            etype=self.DEFAULT_ETYPE,
            detail=detail,
            severity=self.DEFAULT_SEVERITY,
        )

__all__ = [
    "AuthenticationException",
    "AuthorizationException",
    "InvalidRequestException",
    "ObjectNotFoundException",
    "TimeoutException",
    "UnresolvedReferenceException",
    "UnsupportedCapabilityException",
    "QueryException",
]
