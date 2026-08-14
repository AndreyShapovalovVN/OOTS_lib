from typing import Any

from lxml import etree

from oots_lib.lib.xml_utils import clean_attrib, set_element_text


class NS:
    _ns: dict[str, str] = {
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",  # NOSONAR
        "rs": "urn:oasis:names:tc:ebxml-regrep:xsd:rs:4.0",  # NOSONAR
        "rim": "urn:oasis:names:tc:ebxml-regrep:xsd:rim:4.0",  # NOSONAR
        "sdg": "http://data.europa.eu/p4s",  # NOSONAR
        "query": "urn:oasis:names:tc:ebxml-regrep:xsd:query:4.0",  # NOSONAR
        "xlink": "http://www.w3.org/1999/xlink",  # NOSONAR
        "xml": "http://www.w3.org/XML/1998/namespace",  # NOSONAR
    }

    def __init__(self):
        self._xml: etree._Element | None = None

    def _tname(self, ns, tag):
        if not ns:
            return tag
        return f"{{{self._ns[ns]}}}{tag}"

    def _element(
        self,
        ns: str | None,
        tag: str,
        text: Any = None,
        attrib: dict[Any, Any] | None = None,
        nsmap: dict[str, str] | None = None,
    ) -> etree._Element:
        """Створює елемент у просторі імен `ns` з текстом та атрибутами."""
        element = etree.Element(
            self._tname(ns, tag),
            nsmap=self._ns if nsmap is None else nsmap,
            attrib=clean_attrib(attrib or {}),
        )
        set_element_text(element, text)
        return element

    def _subelement(
        self,
        parent: etree._Element,
        ns: str | None,
        tag: str,
        text: Any = None,
        attrib: dict[Any, Any] | None = None,
    ) -> etree._Element:
        """Створює дочірній елемент у просторі імен `ns`."""
        element = etree.SubElement(
            parent,
            self._tname(ns, tag),
            attrib=clean_attrib(attrib or {}),
        )
        set_element_text(element, text)
        return element

    @property
    def xml_tree(self) -> etree._Element | None:
        return self._xml

    @property
    def xml_string(self) -> str:
        if self._xml is None:
            return ''
        xml_bytes: bytes = etree.tostring(self._xml, pretty_print=True)
        return xml_bytes.decode("utf-8")
