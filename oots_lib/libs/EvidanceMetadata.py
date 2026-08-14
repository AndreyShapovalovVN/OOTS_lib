import logging
import uuid

from lxml import etree

from oots_lib.libs.NS import NS


_logger = logging.getLogger(__name__)

__all__ = [
    "EMetadata",
    "IssuingAuthority",
    "IsConformantTo",
    "Distribution",
    "IsAbout",
]

class EMetadata(NS):
    def __init__(self):
        super().__init__()
        self._xml: etree._Element = self._element("sdg", "Evidence")
        self._subelement(self._xml, "sdg", "Identifier", text=uuid.uuid4())

    def issuingAuthority(self, issuingAuthority: etree._Element):   # NOSONAR
        self._xml.append(issuingAuthority)

    def isConformeant(self, isConformeant: etree._Element):   # NOSONAR
        self._xml.append(isConformeant)

    def distribution(self, distribution: etree._Element):
        self._xml.append(distribution)

    def isAbout(self, isAbout: etree._Element):    # NOSONAR
        self._xml.append(isAbout)


class IssuingAuthority(NS):
    def __init__(self, shema, value):
        super().__init__()
        self._xml: etree._Element = self._element("sdg", "IssuingAuthority")
        self._subelement(
            self._xml, "sdg", "Identifier", text=value, attrib={"schemeID": shema}
        )

    def name(self, lang: str, name: str):
        self._subelement(
            self._xml, "sdg", "Name", text=name, attrib={"lang": f"{lang}".upper()}
        )
        return self


class Distribution(NS):
    def __init__(self, content_type):
        super().__init__()
        self._xml: etree._Element = self._element("sdg", "Distribution")
        self._subelement(self._xml, "sdg", "Format", text=content_type)

    def ConformsTo(self, url):
        self._subelement(self._xml, "sdg", "ConformsTo", text=url)

    def Transformation(self, url):
        self._subelement(self._xml, "sdg", "Transformation", text=url)


class IsConformantTo(NS):
    def __init__(self, conformance):
        super().__init__()
        self._xml: etree._Element = self._element("sdg", "IsConformantTo")
        self._subelement(
            self._xml, "sdg", "EvidenceTypeClassification", text=conformance
        )

    def title(self, lang, title):
        self._subelement(
            self._xml, "sdg", "Title", text=title, attrib={"lang": lang.upper()}
        )

    def description(self, lang, description):
        self._subelement(
            self._xml,
            "sdg",
            "Description",
            text=description,
            attrib={"lang": lang.upper()},
        )


class IsAbout(NS):
    def __init__(self, person: etree._Element):
        super().__init__()
        self._xml: etree._Element = self._element("sdg", "IsAbout")
        self._xml.append(person)
