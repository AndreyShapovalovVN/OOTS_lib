import datetime

import pytest
from lxml import etree

from oots_lib.models.Person import (
    Identifier,
    Person,
    _dict_to_person,
    get_person_from_redis,
    save_person_to_redis,
)

SDG = "http://data.europa.eu/p4s"

PERSON_XML = f"""
<sdg:Person xmlns:sdg="{SDG}">
  <sdg:LevelOfAssurance>Substantial</sdg:LevelOfAssurance>
  <sdg:Identifier schemeID="eidas">UA/UA/1234567890</sdg:Identifier>
  <sdg:FamilyName nonLatin="Шевченко">Shevchenko</sdg:FamilyName>
  <sdg:GivenName nonLatin="Тарас">Taras</sdg:GivenName>
  <sdg:AdditionalName nonLatin="Григорович">Hryhorovych</sdg:AdditionalName>
  <sdg:BirthName nonLatin="Шевченко">Shevchenko</sdg:BirthName>
  <sdg:DateOfBirth>1814-03-09</sdg:DateOfBirth>
  <sdg:Gender>Male</sdg:Gender>
  <sdg:Nationality>UA</sdg:Nationality>
  <sdg:CountryOfBirth>UA</sdg:CountryOfBirth>
  <sdg:TownOfBirth>Moryntsi</sdg:TownOfBirth>
  <sdg:CountryOfResidence>UA</sdg:CountryOfResidence>
</sdg:Person>
"""


class RedisStub:
    def __init__(self, value=None):
        self.value = value
        self.saved: list[tuple[str, object]] = []

    async def save_to_redis(self, key, value):
        self.saved.append((key, value))
        self.value = value

    async def get_from_redis(self, key):
        return self.value


def make_person() -> Person:
    return Person(
        identifier=Identifier("UA/UA/1234567890"),
        FamilyName="Shevchenko",
        FamilyNameNonLatin="Шевченко",
        GivenName="Taras",
        DateOfBirth=datetime.date(1814, 3, 9),
        Gender="Male",
    )


def test_identifier_defaults_to_empty_value():
    identifier = Identifier()
    assert identifier.value is None
    assert identifier.schemeID == "eidas"
    assert identifier.country_identifier == identifier.country_nationality


def test_identifier_parses_composite_value():
    identifier = Identifier("PL/UA/1234567890", schemeID="custom")

    assert identifier.country_identifier == "PL"
    assert identifier.country_nationality == "UA"
    assert identifier.identifier == "1234567890"
    assert identifier.value == "PL/UA/1234567890"
    assert identifier.schemeID == "custom"


def test_identifier_scheme_falls_back_to_eidas():
    assert Identifier("UA/UA/1", schemeID=None).schemeID == "eidas"


@pytest.mark.parametrize("value", ["1234567890", "UA/1234567890", "UA/UA/UA/1"])
def test_identifier_rejects_malformed_value(value):
    with pytest.raises(ValueError, match="country/country_nationality/identifier"):
        Identifier(value)


def test_identifier_value_reset_to_none():
    identifier = Identifier("UA/UA/1234567890")
    identifier.value = None
    assert identifier.identifier is None
    assert identifier.value is None


def test_identifier_element_in_sdg_namespace():
    element = Identifier("UA/UA/1234567890").get_element()

    assert element.tag == f"{{{SDG}}}Identifier"
    assert element.get("schemeID") == "eidas"
    assert element.text == "UA/UA/1234567890"


def test_identifier_element_without_sdg_uses_bare_identifier():
    element = Identifier("UA/UA/1234567890").get_element(sdg=False)

    assert element.tag == "Identifier"
    assert element.text == "1234567890"


def test_person_field_parsers_tolerate_missing_elements():
    assert Person._parse_name(None) == (None, None)
    assert Person._get_id(None) == (None, None)
    assert Person._get_text(None) is None


def test_person_get_element_without_non_latin_names():
    person = Person(FamilyName="Shevchenko", GivenName="Taras", AdditionalName="H", BirthName="S")
    element = person.get_element()

    for tag in ("FamilyName", "GivenName", "AdditionalName", "BirthName"):
        child = element.find(f"{{{SDG}}}{tag}")
        assert child is not None
        assert child.get("nonLatin") is None


def test_person_get_element_with_string_date_of_birth():
    element = Person(DateOfBirth="1814-03-09").get_element()  # type: ignore[arg-type]

    assert element.find(f"{{{SDG}}}DateOfBirth").text == "1814-03-09"


def test_person_xml_setter_parses_all_fields():
    person = Person()
    person.xml = PERSON_XML

    assert person.LevelOfAssurance == "Substantial"
    assert person.identifier is not None
    assert person.identifier.value == "UA/UA/1234567890"
    assert person.identifier.schemeID == "eidas"
    assert person.FamilyName == "Shevchenko"
    assert person.FamilyNameNonLatin == "Шевченко"
    assert person.GivenName == "Taras"
    assert person.AdditionalNameNonLatin == "Григорович"
    assert person.BirthName == "Shevchenko"
    assert person.DateOfBirth == datetime.date(1814, 3, 9)
    assert person.Gender == "Male"
    assert person.Nationality == "UA"
    assert person.CountryOfBirth == "UA"
    assert person.TownOfBirth == "Moryntsi"
    assert person.CountryOfResidence == "UA"
    assert person.xml_tree is not None


def test_person_xml_setter_accepts_element():
    person = Person()
    person.xml = etree.fromstring(PERSON_XML.strip().encode("utf-8"))
    assert person.GivenName == "Taras"


def test_person_xml_setter_rejects_other_types():
    with pytest.raises(TypeError, match="str"):
        Person().xml = 42  # type: ignore[assignment]


def test_person_get_element_roundtrips_through_xml_setter():
    person = make_person()
    element = person.get_element()

    parsed = Person()
    parsed.xml = element

    assert parsed.FamilyName == "Shevchenko"
    assert parsed.FamilyNameNonLatin == "Шевченко"
    assert parsed.DateOfBirth == datetime.date(1814, 3, 9)
    assert element.tag == f"{{{SDG}}}Person"


def test_person_xml_property_is_serialized_element():
    xml = make_person().xml
    assert "<sdg:GivenName>Taras</sdg:GivenName>" in xml


def test_person_get_dict_uses_camel_case_keys():
    data = make_person().get_dict()

    assert data["identifier"] == {"value": "UA/UA/1234567890", "schemeID": "eidas"}
    assert data["DateOfBirth"] == "1814-03-09"
    assert data["LevelOfAssurance"] == "High"


def test_person_get_dict_without_identifier():
    assert Person().get_dict()["identifier"] is None


def test_person_legacy_dict_uses_snake_case_keys():
    data = make_person().dict

    assert data["eidas_identifier"] == "UA/UA/1234567890"
    assert data["family_name_non_latin"] == "Шевченко"
    assert data["date_of_birth"] == "1814-03-09"
    assert Person().dict["eidas_identifier"] is None


def test_set_from_dict_accepts_camel_case():
    person = Person.set_from_dict(
        {
            "LevelOfAssurance": "Substantial",
            "identifier": {"value": "UA/UA/1", "schemeID": "custom"},
            "FamilyName": "Shevchenko",
            "DateOfBirth": "1814-03-09",
        }
    )

    assert person.LevelOfAssurance == "Substantial"
    assert person.identifier is not None
    assert person.identifier.schemeID == "custom"
    assert person.DateOfBirth == datetime.date(1814, 3, 9)


def test_set_from_dict_accepts_legacy_keys():
    person = Person.from_dict(
        {
            "level_of_assurance": "Low",
            "eidas_identifier": "UA/UA/1",
            "family_name": "Shevchenko",
            "given_name": "Taras",
            "date_of_birth": "1814-03-09",
            "country_of_residence": "UA",
        }
    )

    assert person.LevelOfAssurance == "Low"
    assert person.identifier is not None
    assert person.identifier.value == "UA/UA/1"
    assert person.GivenName == "Taras"
    assert person.CountryOfResidence == "UA"


@pytest.mark.parametrize(
    "identifier_input",
    ["UA/UA/1", Identifier("UA/UA/1"), {"value": "UA/UA/1"}],
)
def test_set_from_dict_identifier_variants(identifier_input):
    person = Person.set_from_dict({"identifier": identifier_input})
    assert person.identifier is not None
    assert person.identifier.value == "UA/UA/1"


def test_set_from_dict_without_identifier():
    assert Person.set_from_dict({}).identifier is None


def test_set_from_dict_level_of_assurance_defaults_to_high():
    assert Person.set_from_dict({"LevelOfAssurance": None}).LevelOfAssurance == "High"


def test_set_from_dict_rejects_non_dict():
    with pytest.raises(TypeError, match="dict"):
        Person.set_from_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_dict_setter_replaces_all_fields():
    person = make_person()
    person.dict = {"family_name": "Franko", "given_name": "Ivan"}

    assert person.FamilyName == "Franko"
    assert person.GivenName == "Ivan"
    assert person.DateOfBirth is None
    assert person.identifier is None


def test_dict_to_person_roundtrip():
    person = make_person()
    assert _dict_to_person(person.dict).dict == person.dict


async def test_save_person_to_redis():
    redis = RedisStub()
    person = make_person()

    await save_person_to_redis(redis, "key", person)

    assert redis.saved == [("key", person.dict)]


async def test_save_person_rejects_wrong_type():
    with pytest.raises(TypeError, match="Person"):
        await save_person_to_redis(RedisStub(), "key", {"family_name": "x"})  # type: ignore[arg-type]


async def test_get_person_from_redis_roundtrip():
    person = make_person()
    restored = await get_person_from_redis(RedisStub(person.dict), "key")

    assert restored is not None
    assert restored.dict == person.dict


async def test_get_person_from_redis_supports_legacy_list():
    person = make_person()
    restored = await get_person_from_redis(RedisStub([person.dict]), "key")

    assert restored is not None
    assert restored.FamilyName == "Shevchenko"


async def test_get_person_from_redis_returns_none():
    assert await get_person_from_redis(RedisStub(None), "key") is None
    assert await get_person_from_redis(RedisStub([]), "key") is None


async def test_get_person_from_redis_rejects_bad_payload():
    with pytest.raises(ValueError, match="str"):
        await get_person_from_redis(RedisStub("broken"), "key")


async def test_person_from_redis_updates_instance():
    person = Person()
    await person.from_redis(RedisStub(make_person().dict), "key")

    assert person.FamilyName == "Shevchenko"


async def test_person_from_redis_keeps_state_when_key_missing():
    person = make_person()
    await person.from_redis(RedisStub(None), "key")

    assert person.FamilyName == "Shevchenko"
