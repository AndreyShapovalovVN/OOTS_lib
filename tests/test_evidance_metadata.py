import uuid

from lxml import etree

from oots_lib.lib.EvidanceMetadata import (
    Distribution,
    EMetadata,
    IsAbout,
    IsConformantTo,
    IssuingAuthority,
)

SDG = "http://data.europa.eu/p4s"


def tag(name: str) -> str:
    return f"{{{SDG}}}{name}"


def test_emetadata_root_has_generated_identifier():
    metadata = EMetadata()
    root = metadata.xml_tree

    assert root is not None
    assert root.tag == tag("Evidence")
    identifiers = root.findall(tag("Identifier"))
    assert len(identifiers) == 1
    uuid.UUID(identifiers[0].text)


def test_emetadata_identifiers_are_unique():
    first = EMetadata().xml_tree
    second = EMetadata().xml_tree
    assert first is not None and second is not None
    assert first.find(tag("Identifier")).text != second.find(tag("Identifier")).text


def test_emetadata_appends_children_in_call_order():
    metadata = EMetadata()
    authority = IssuingAuthority("urn:scheme", "42").xml_tree
    conformant = IsConformantTo("urn:conformance").xml_tree
    distribution = Distribution("application/pdf").xml_tree
    person = etree.Element(tag("Person"))
    about = IsAbout(person).xml_tree

    assert authority is not None and conformant is not None
    assert distribution is not None and about is not None

    metadata.issuingAuthority(authority)
    metadata.isConformeant(conformant)
    metadata.distribution(distribution)
    metadata.isAbout(about)

    root = metadata.xml_tree
    assert root is not None
    assert [child.tag for child in root] == [
        tag("Identifier"),
        tag("IssuingAuthority"),
        tag("IsConformantTo"),
        tag("Distribution"),
        tag("IsAbout"),
    ]


def test_issuing_authority_identifier_and_name():
    authority = IssuingAuthority("urn:scheme", 42)
    assert authority.name(lang="ua", name="ДРАЦС") is authority

    root = authority.xml_tree
    assert root is not None
    identifier = root.find(tag("Identifier"))
    assert identifier is not None
    assert identifier.get("schemeID") == "urn:scheme"
    assert identifier.text == "42"

    name = root.find(tag("Name"))
    assert name is not None
    assert name.get("lang") == "UA"
    assert name.text == "ДРАЦС"


def test_distribution_format_conforms_to_and_transformation():
    distribution = Distribution("application/pdf")
    distribution.ConformsTo("urn:conforms")
    distribution.Transformation("urn:transform")

    root = distribution.xml_tree
    assert root is not None
    assert root.find(tag("Format")).text == "application/pdf"
    assert root.find(tag("ConformsTo")).text == "urn:conforms"
    assert root.find(tag("Transformation")).text == "urn:transform"


def test_is_conformant_to_holds_evidence_type_classification():
    root = IsConformantTo("urn:conformance").xml_tree

    assert root is not None
    assert root.tag == tag("IsConformantTo")
    assert root.find(tag("EvidenceTypeClassification")).text == "urn:conformance"


def test_is_about_wraps_person_element():
    person = etree.Element(tag("Person"))
    etree.SubElement(person, tag("GivenName")).text = "Taras"

    root = IsAbout(person).xml_tree

    assert root is not None
    assert root.tag == tag("IsAbout")
    assert root[0] is person


def test_xml_string_is_serializable_for_metadata():
    xml = EMetadata().xml_string
    assert xml.startswith("<sdg:Evidence")
    assert etree.fromstring(xml.encode("utf-8")).tag == tag("Evidence")
