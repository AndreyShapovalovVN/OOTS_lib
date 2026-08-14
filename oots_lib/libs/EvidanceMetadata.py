import logging
import uuid

from lxml import etree

from oots_lib.lib.NS import NS


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
        self._xml: etree._Element = etree.Element(self._tname("sdg", "Evidence"), nsmap=self._ns)
        etree.SubElement(self._xml, self._tname("sdg", "Identifier")).text = str(uuid.uuid4())

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
        self._xml: etree._Element = etree.Element(self._tname("sdg", "IssuingAuthority"), nsmap=self._ns)
        etree.SubElement(self._xml, self._tname("sdg", "Identifier"),
                         attrib={'schemeID': shema}).text = f"{value}"

    def name(self, lang: str, name: str):
        etree.SubElement(self._xml, self._tname('sdg', 'Name'),
                         attrib={'lang': f"{lang}".upper()}).text = f"{name}"
        return self


class Distribution(NS):
    def __init__(self, content_type):
        super().__init__()
        self._xml: etree._Element = etree.Element(self._tname("sdg", "Distribution"), nsmap=self._ns)
        etree.SubElement(self._xml, self._tname("sdg", "Format")).text = content_type

    def ConformsTo(self, url):
        etree.SubElement(self._xml, self._tname("sdg", "ConformsTo")).text = url

    def Transformation(self, url):
        etree.SubElement(self._xml, self._tname("sdg", "Transformation")).text = url


class IsConformantTo(NS):
    def __init__(self, conformance):
        super().__init__()
        self._xml: etree._Element = etree.Element(self._tname("sdg", "IsConformantTo"), nsmap=self._ns)
        etree.SubElement(self._xml, self._tname("sdg", "EvidenceTypeClassification")).text = conformance

    def title(self, lang, title):
        etree.SubElement(self._xml, self._tname('sdg', 'Title'),
                         attrib={'lang': lang.upper}).text = title

    def description(self, lang, description):
        etree.SubElement(self._xml, self._tname('sdg', 'Description'),
                         attrib={'lang': lang.upper}).text = description


class IsAbout(NS):
    def __init__(self, person: etree._Element):
        super().__init__()
        self._xml: etree._Element = etree.Element(self._tname("sdg", "IsAbout"), nsmap=self._ns)
        self._xml.append(person)
