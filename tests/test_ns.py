import pytest
from lxml import etree

from oots_lib.lib.NS import NS


def test_tname_builds_qualified_name():
    assert NS()._tname("sdg", "Evidence") == "{http://data.europa.eu/p4s}Evidence"


def test_tname_without_namespace_returns_plain_tag():
    assert NS()._tname("", "Evidence") == "Evidence"
    assert NS()._tname(None, "Evidence") == "Evidence"


def test_tname_rejects_unknown_prefix():
    with pytest.raises(KeyError):
        NS()._tname("unknown", "Evidence")


def test_xml_tree_and_string_default_to_empty():
    ns = NS()
    assert ns.xml_tree is None
    assert ns.xml_string == ""


def test_xml_string_serializes_tree():
    ns = NS()
    ns._xml = etree.Element(ns._tname("sdg", "Evidence"), nsmap={"sdg": ns._ns["sdg"]})
    etree.SubElement(ns._xml, ns._tname("sdg", "Identifier")).text = "id-1"

    xml = ns.xml_string
    assert xml.startswith("<sdg:Evidence")
    assert "<sdg:Identifier>id-1</sdg:Identifier>" in xml
    assert ns.xml_tree is ns._xml
