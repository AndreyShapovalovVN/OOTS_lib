import pytest
from lxml import etree

from oots_lib.lib.exceptions import (
    AuthenticationException,
    AuthorizationException,
    EDMException,
    InvalidRequestException,
    ObjectNotFoundException,
    QueryException,
    TimeoutException,
    UnresolvedReferenceException,
    UnsupportedCapabilityException,
)

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


def test_default_message_when_nothing_provided():
    assert str(EDMException()) == "EDMException"


def test_message_formatting_includes_code_and_detail():
    exc = EDMException(message="Broken", code="EDM:ERR:0001", detail="ключ відсутній")
    assert str(exc) == "[EDM:ERR:0001] Broken : ключ відсутній"


def test_default_severity_applied():
    assert EDMException().severity == EDMException.DEFAULT_SEVERITY
    assert EDMException(severity="custom").severity == "custom"


def test_xml_contains_only_non_none_attributes():
    exc = EDMException(message="Broken", code="EDM:ERR:0001", etype="rs:SomeType")
    element = exc.xml

    assert element.tag == "{urn:oasis:names:tc:ebxml-regrep:xsd:rs:4.0}Exception"
    assert element.get("message") == "Broken"
    assert element.get("code") == "EDM:ERR:0001"
    assert element.get(XSI_TYPE) == "rs:SomeType"
    assert element.get("severity") == EDMException.DEFAULT_SEVERITY
    assert "detail" not in element.attrib


def test_xml_is_cached():
    exc = EDMException(message="Broken")
    assert exc.xml is exc.xml


def test_xml_is_not_shared_between_instances():
    first = EDMException(message="first")
    second = EDMException(message="second")
    assert first.xml is not second.xml
    assert second.xml.get("message") == "second"


def test_clean_attrib_stringifies_values():
    assert EDMException._clean_attrib({"a": 1, "b": None, "c": "x"}) == {"a": "1", "c": "x"}


def test_to_pretty_xml_is_parsable():
    exc = InvalidRequestException(detail="поле відсутнє")
    pretty = exc.to_pretty_xml()

    assert isinstance(pretty, str)
    parsed = etree.fromstring(pretty.encode("utf-8"))
    assert parsed.get("detail") == "поле відсутнє"


@pytest.mark.parametrize(
    ("exc_class", "code", "etype"),
    [
        (AuthenticationException, "EDM:ERR:0001", "rs:AuthenticationExceptionType"),
        (AuthorizationException, "EDM:ERR:0002", "rs:AuthorizationExceptionType"),
        (InvalidRequestException, "EDM:ERR:0003", "rs:InvalidRequestExceptionType"),
        (ObjectNotFoundException, "EDM:ERR:0004", "rs:ObjectNotFoundExceptionType"),
        (TimeoutException, "EDM:ERR:0005", "rs:TimeoutExceptionType"),
        (UnresolvedReferenceException, "EDM:ERR:0006", "rs:UnresolvedReferenceExceptionType"),
        (UnsupportedCapabilityException, "EDM:ERR:0007", "rs:UnsupportedCapabilityExceptionType"),
        (QueryException, "EDM:ERR:0008", "query:QueryExceptionType"),
    ],
)
def test_concrete_exceptions_defaults(exc_class, code, etype):
    exc = exc_class(detail="деталі")

    assert isinstance(exc, EDMException)
    assert exc.code == code
    assert exc.e_type == etype
    assert exc.message == exc_class.DEFAULT_MESSAGE
    assert exc.severity == exc_class.DEFAULT_SEVERITY
    assert exc.xml.get(XSI_TYPE) == etype
    assert exc.xml.get("detail") == "деталі"


@pytest.mark.parametrize(
    "exc_class",
    [AuthenticationException, AuthorizationException, InvalidRequestException, QueryException],
)
def test_message_can_be_overridden(exc_class):
    assert exc_class(message="custom").message == "custom"
