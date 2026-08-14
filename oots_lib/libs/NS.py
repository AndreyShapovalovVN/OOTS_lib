from lxml import etree


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

    @property
    def xml_tree(self) -> etree._Element | None:
        return self._xml

    @property
    def xml_string(self) -> str:
        if self._xml is None:
            return ''
        xml_bytes: bytes = etree.tostring(self._xml, pretty_print=True)
        return xml_bytes.decode("utf-8")
