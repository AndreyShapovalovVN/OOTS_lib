import datetime
import json
from dataclasses import dataclass
from typing import ClassVar

import pytest
from lxml import etree

import oots_lib.models.Base as base_module
from oots_lib.models.Base import Base, MainBase


@dataclass
class Sample(MainBase):
    serialization_fields: ClassVar[tuple[str, ...]] = ("name", "active")
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
        serialization_fields: ClassVar[tuple[str, ...]] = (*Sample.serialization_fields, "day")
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
        serialization_fields: ClassVar[tuple[str, ...]] = ("value",)
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


@dataclass
class Selected(MainBase):
    serialization_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: str = "public"
    secret: str = "private"


def test_allowlist_controls_both_formats_and_inherited_fields():
    @dataclass
    class Extended(Selected):
        internal: str = "hidden"

    model = Extended(_name_="record")
    assert model.get_dict() == {"name": "public"}
    assert json.loads(model.get_json()) == {"record": {"name": "public"}}
    assert etree.tostring(model.get_element()) == b"<Extended><name>public</name></Extended>"
    assert "private" not in model.get_xml()
    assert "hidden" not in model.get_xml()


def test_empty_allowlist_exports_no_fields():
    @dataclass
    class Empty(MainBase):
        secret: str = "private"

    model = Empty()
    assert model.get_dict() == {}
    assert json.loads(model.get_json()) == {}
    assert len(model.get_element()) == 0


def test_nested_allowlists_apply_in_lists_and_dicts():
    @dataclass
    class Container(MainBase):
        serialization_fields: ClassVar[tuple[str, ...]] = ("children", "mapping")
        children: object = None
        mapping: object = None

    model = Container(children=[Selected()], mapping={"child": Selected()})
    expected = {"children": [{"name": "public"}], "mapping": {"child": {"name": "public"}}}
    assert model.get_dict() == expected
    assert json.loads(model.get_json()) == expected
    root = etree.fromstring(model.get_xml().encode())
    assert root.findtext("children/name") == "public"
    assert root.findtext("mapping/child/name") == "public"
    assert "private" not in model.get_xml()


@pytest.mark.parametrize("method", ["get_dict", "get_xml"])
def test_unlisted_values_are_not_copied_or_serialized(method):
    class CannotCopy:
        def __deepcopy__(self, memo):
            raise AssertionError("Excluded field was accessed")

    model = Selected(secret=CannotCopy())
    getattr(model, method)()


@pytest.mark.parametrize("method", ["get_dict", "get_xml"])
def test_plain_nested_dataclass_requires_explicit_serialization_fields(method):
    @dataclass
    class Unsafe:
        secret: str = "private"

    model = Selected(name=Unsafe())
    with pytest.raises(TypeError, match="serialization_fields"):
        getattr(model, method)()


@pytest.mark.parametrize("method", ["get_dict", "get_xml"])
def test_allowlist_rejects_service_fields(method):
    class Invalid(Selected):
        serialization_fields = ("_name_",)

    with pytest.raises(ValueError, match="_name_"):
        getattr(Invalid(), method)()
