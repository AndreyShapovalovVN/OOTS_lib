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

    def xml(self) -> etree._Element | None:
        """
        Returns an XML element with cleaned-up namespaces.

        This method processes the stored XML element to ensure that any namespaces
        are properly cleaned and adjusted using the provided namespace map. If no
        XML element is stored, the method returns None.

        :return: The processed XML element with cleaned namespaces, or None if no XML
            element is stored.
        :rtype: etree._Element | None
        """
        if self._xml is None:
            return None
        etree.cleanup_namespaces(self._xml, top_nsmap=self._ns)
        return self._xml

    @property
    def xml_tree(self) -> etree._Element | None:
        """
        Provides access to the XML tree representation for this object.

        The XML tree is represented as an `etree._Element` instance. If the
        XML tree has not been initialized or assigned, this property will
        return `None`.

        :rtype: etree._Element | None
        :return: The root element of the XML tree, or `None` if no XML tree
            is available.
        """
        return self._xml

    @property
    def xml_string(self) -> str:
        """
        Returns the XML content as a formatted string. If there is no XML content,
        an empty string is returned.

        :return: The XML content formatted as a string, or an empty string if no XML is present.
        :rtype: str
        """
        if self._xml is None:
            return ''
        xml_bytes: bytes = etree.tostring(self._xml, pretty_print=True)
        return xml_bytes.decode("utf-8")
