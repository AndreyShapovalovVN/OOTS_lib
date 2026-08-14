import pytest
from lxml import etree

from oots_lib.lib.xml_safety import safe_fromstring, safe_parse, safe_parser


def test_safe_parser_disables_entity_resolution_and_network():
    parser = safe_parser()

    assert parser.resolvers is not None
    root = etree.fromstring("<root><a>1</a></root>", parser=parser)
    assert root.find("a").text == "1"


def test_safe_fromstring_accepts_plain_xml():
    root = safe_fromstring(b"<root><a>1</a></root>")

    assert root.tag == "root"


def test_safe_fromstring_accepts_str_input():
    root = safe_fromstring("<root/>")

    assert root.tag == "root"


def test_safe_fromstring_rejects_internal_dtd():
    xml = b'<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x "y">]><root/>'

    with pytest.raises(ValueError, match="DOCTYPE"):
        safe_fromstring(xml)


def test_safe_fromstring_rejects_external_dtd():
    xml = b'<?xml version="1.0"?><!DOCTYPE root SYSTEM "http://example.com/e.dtd"><root/>'

    with pytest.raises(ValueError, match="DOCTYPE"):
        safe_fromstring(xml)


def test_safe_fromstring_does_not_expand_external_entity(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret")
    xml = (
        '<?xml version="1.0"?>'
        f'<!DOCTYPE root [<!ENTITY xxe SYSTEM "file://{secret}">]>'
        "<root>&xxe;</root>"
    ).encode()

    with pytest.raises(ValueError, match="DOCTYPE"):
        safe_fromstring(xml)


def test_safe_parse_reads_file(tmp_path):
    path = tmp_path / "doc.xml"
    path.write_text("<root><a>1</a></root>")

    tree = safe_parse(path)

    assert tree.getroot().tag == "root"


def test_safe_parse_accepts_str_path(tmp_path):
    path = tmp_path / "doc.xml"
    path.write_text("<root/>")

    assert safe_parse(str(path)).getroot().tag == "root"


def test_safe_parse_rejects_dtd(tmp_path):
    path = tmp_path / "doc.xml"
    path.write_text('<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x "y">]><root/>')

    with pytest.raises(ValueError, match="DOCTYPE"):
        safe_parse(path)


def test_safe_fromstring_raises_on_malformed_xml():
    with pytest.raises(etree.XMLSyntaxError):
        safe_fromstring("<root>")
