import datetime
import json
from dataclasses import dataclass

import pytest
from lxml import etree

import oots_lib.models.Base as base_module
from oots_lib.models.Base import Base, MainBase


@dataclass
class Sample(MainBase):
    name: str = "Іван"
    active: bool = True

    def get_element(self) -> etree._Element:
        root = etree.Element("Sample")
        self._set_text(etree.SubElement(root, "name"), self.name)
        self._set_text(etree.SubElement(root, "active"), self.active)
        return root


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, "true"),
        (False, "false"),
        ("текст", "текст"),
        (5, "5"),
        (datetime.date(2024, 5, 1), "2024-05-01"),
        (datetime.datetime(2024, 5, 1, 10, 30), "2024-05-01T10:30:00"),
    ],
)
def test_set_text(value, expected):
    element = etree.Element("x")
    Base._set_text(element, value)
    assert element.text == expected


@pytest.mark.parametrize("value", [None, "", {}])
def test_parse_date_empty_values(value):
    assert Base._parse_date(value) is None


def test_parse_date_from_string_and_date():
    assert Base._parse_date("2024-05-01") == datetime.date(2024, 5, 1)
    assert Base._parse_date(datetime.date(2024, 5, 1)) == datetime.date(2024, 5, 1)


def test_parse_date_invalid_value():
    with pytest.raises(ValueError):
        Base._parse_date("01.05.2024")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (None, False),
        ("true", True),
        (" TRUE ", True),
        ("false", False),
        ("щось", False),
        (1, False),
    ],
)
def test_parse_bool(value, expected):
    assert Base._parse_bool(value) is expected


def test_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Base()  # type: ignore[abstract]


@pytest.mark.parametrize("root_name", [None, "", "Документ"])
def test_get_xml_serializes_element(root_name):
    xml = Sample(_name_=root_name).get_xml()
    assert etree.fromstring(xml.encode()).tag == "Sample"
    assert "_name_" not in xml
    assert "<name>Іван</name>" in xml
    assert "<active>true</active>" in xml


def test_get_dict_and_get_json():
    sample = Sample(name="Ivan", active=False)
    assert sample.get_dict() == {"name": "Ivan", "active": False}
    assert json.loads(sample.get_json()) == {"name": "Ivan", "active": False}


@pytest.mark.parametrize("root_name", [None, "", "Документ"])
def test_get_json_keeps_non_ascii_and_serializes_dates(root_name):
    @dataclass
    class WithDate(Sample):
        day: datetime.date = datetime.date(2024, 5, 1)

    payload = WithDate(_name_=root_name).get_json()
    assert "Іван" in payload
    data = json.loads(payload)
    if root_name:
        assert root_name in payload
        data = data[root_name]
    assert data == {"name": "Іван", "active": True, "day": "2024-05-01"}


def test_set_from_dict_not_implemented():
    with pytest.raises(NotImplementedError):
        MainBase.set_from_dict({})


def test_get_pdf_delegates_to_generator(monkeypatch):
    captured = {}

    def fake_generate(rdf, xslt_file, css):
        captured.update(rdf=rdf, xslt_file=xslt_file, css=css)
        return b"%PDF-1.7"

    monkeypatch.setattr(base_module, "generate_pdf_from_xslt", fake_generate)

    sample = Sample()
    assert sample.get_pdf("style.xsl", css=["body {}"]) == b"%PDF-1.7"
    assert captured["rdf"] == sample.get_xml()
    assert captured["xslt_file"] == "style.xsl"
    assert captured["css"] == ["body {}"]


@pytest.mark.parametrize("name", [None, "", "Документ"])
def test_get_json_optional_name(name):
    sample = Sample(_name_=name)
    fields = {"name": "Іван", "active": True}
    assert sample.get_dict() == fields
    assert json.loads(sample.get_json()) == ({name: fields} if name else fields)


def test_get_json_name_with_overridden_get_dict():
    from oots_lib.models.Person import Person

    person = Person(_name_="Person", GivenName="Іван")
    assert json.loads(person.get_json()) == {"Person": person.get_dict()}


def test_main_base_name_allows_required_subclass_fields():
    @dataclass
    class Required(MainBase):
        value: int

        def get_element(self):
            return etree.Element("Required")

    assert json.loads(Required(7, _name_="record").get_json()) == {"record": {"value": 7}}


def test_get_json_uses_updated_root_name():
    sample = Sample()
    fields = {"name": "Іван", "active": True}
    assert sample._name_ is None
    assert json.loads(sample.get_json()) == fields

    sample._name_ = "record"
    assert json.loads(sample.get_json()) == {"record": fields}
    assert sample.get_dict() == fields
    assert sample._name_ == "record"

    sample._name_ = ""
    assert json.loads(sample.get_json()) == fields
