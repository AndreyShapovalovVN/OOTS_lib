import datetime
import logging
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from oots_lib.libs.NS import NS
from oots_lib.libs.redis_serde import load_model_from_redis, save_model_to_redis
from oots_lib.libs.xml_safety import safe_fromstring
from oots_lib.models.Base import Base, MainBase
from oots_lib.import_env import import_env


_logger = logging.getLogger(__name__)

COUNTRY = import_env("COUNTRY")

__all__ = [
    "Identifier",
    "Person",
    "save_person_to_redis",
    "get_person_from_redis",
]

@dataclass(init=False)
class Identifier(Base, NS):
    """Ідентифікатор у форматі `country/country_nationality/identifier`."""

    country_identifier: str = COUNTRY
    country_nationality: str = COUNTRY
    identifier: str | None = None
    schemeID: str = "eidas"

    def __init__(self, value: str | None = None, schemeID: str | None = "eidas"):     # NOSONAR
        super().__init__()
        self.country_identifier = COUNTRY
        self.country_nationality = COUNTRY
        self.identifier = None
        self.schemeID = schemeID or "eidas"
        self.value = value

    def get_element(self, sdg: bool=True) -> etree._Element:
        if sdg:
            return self._element(
                "sdg",
                "Identifier",
                text=self.value,
                attrib={"schemeID": self.schemeID},
                nsmap={"sdg": self._ns["sdg"]},
            )
        return self._element(None, "Identifier", text=self.identifier, nsmap={})

    @property
    def value(self) -> str | None:
        """Повертає повне значення ідентифікатора або `None`."""
        ci = self.country_identifier
        cn = self.country_nationality
        ident = self.identifier
        if ci is None or cn is None or ident is None:
            return None
        return f"{ci}/{cn}/{ident}"

    @value.setter
    def value(self, value: str | None) -> None:
        if value is None:
            self.identifier = None
            return

        parts = value.split("/")
        if len(parts) != 3:
            raise ValueError("Значення має бути у форматі 'country/country_nationality/identifier'")

        self.country_identifier, self.country_nationality, self.identifier = parts


@dataclass
class Person(MainBase, NS):
    LevelOfAssurance: str = "High"
    identifier: Identifier | None = None  # РНОКПП
    FamilyName: str | None = None  # Призвище
    FamilyNameNonLatin: str | None = None
    GivenName: str | None = None  # Ім'я
    GivenNameNonLatin: str | None = None
    AdditionalName: str | None = None  # по Батькові
    AdditionalNameNonLatin: str | None = None
    BirthName: str | None = None
    BirthNameNonLatin: str | None = None
    DateOfBirth: datetime.date | None = None
    Gender: str | None = None
    Nationality: str | None = None
    CountryOfBirth: str | None = None
    TownOfBirth: str | None = None
    CountryOfResidence: str | None = None
    _xml: etree._Element | None = field(init=False, repr=False, default=None)
    _ns = {"sdg": "http://data.europa.eu/p4s"}  # NOSONAR

    # Поля з атрибутом nonLatin: значення у `<Name>`, транслітерація у `NameNonLatin`.
    _NAME_FIELDS = ("FamilyName", "GivenName", "AdditionalName", "BirthName")
    # Поля, які серіалізуються як простий текстовий елемент.
    _TEXT_FIELDS = (
        "Gender",
        "Nationality",
        "CountryOfBirth",
        "TownOfBirth",
        "CountryOfResidence",
    )
    # Відповідність між іменами полів моделі та легасі snake_case-ключами.
    _FIELD_ALIASES = (
        ("LevelOfAssurance", "level_of_assurance"),
        ("identifier", "eidas_identifier"),
        ("FamilyName", "family_name"),
        ("FamilyNameNonLatin", "family_name_non_latin"),
        ("GivenName", "given_name"),
        ("GivenNameNonLatin", "given_name_non_latin"),
        ("AdditionalName", "additional_name"),
        ("AdditionalNameNonLatin", "additional_name_non_latin"),
        ("BirthName", "birth_name"),
        ("BirthNameNonLatin", "birth_name_non_latin"),
        ("DateOfBirth", "date_of_birth"),
        ("Gender", "gender"),
        ("Nationality", "nationality"),
        ("CountryOfBirth", "country_of_birth"),
        ("TownOfBirth", "town_of_birth"),
        ("CountryOfResidence", "country_of_residence"),
    )

    def __post_init__(self) -> None:
        self._xml = None

    @staticmethod
    def _parse_name(element: etree._Element):
        if element is None:
            return None, None
        return element.text, element.get("nonLatin")

    @staticmethod
    def _get_id(element: etree._Element):
        if element is None:
            return None, None
        return element.text, element.get("schemeID")

    @staticmethod
    def _get_text(element: etree._Element):
        if element is None:
            return None
        return element.text

    def _find(self, root: etree._Element, tag: str):
        return root.find(f".//sdg:{tag}", self._ns)  # type: ignore[arg-type]

    def _find_text(self, root: etree._Element, tag: str):
        return self._get_text(self._find(root, tag))

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        return value.isoformat() if isinstance(value, datetime.date) else value

    @property
    def xml(self) -> str:
        return self.get_xml()

    @xml.setter
    def xml(self, xml: str | bytes | etree._Element) -> None:
        if isinstance(xml, str | bytes):
            root = safe_fromstring(xml)
            _logger.debug("XML зчитано")
        elif isinstance(xml, etree._Element):
            root = xml
            _logger.debug("XML зчитано")
        else:
            raise TypeError("xml має бути str або bytes")

        _logger.debug("Парсинг значень")
        self.LevelOfAssurance = self._find_text(root, "LevelOfAssurance")
        self.identifier = Identifier(*self._get_id(self._find(root, "Identifier")))

        for name in self._NAME_FIELDS:
            value, non_latin = self._parse_name(self._find(root, name))
            setattr(self, name, value)
            setattr(self, f"{name}NonLatin", non_latin)

        self.DateOfBirth = self._parse_date(self._find_text(root, "DateOfBirth"))

        for tag in self._TEXT_FIELDS:
            setattr(self, tag, self._find_text(root, tag))

        self._xml = root
        _logger.debug("Дані зчитані")

    @property
    def xml_tree(self) -> etree._Element | None:
        return self.get_element()

    def get_element(self) -> etree._Element:
        root = self._element("sdg", "Person")

        self._subelement(root, "sdg", "LevelOfAssurance", text=self.LevelOfAssurance)

        if self.identifier is not None and self.identifier.value:
            root.append(self.identifier.get_element(sdg=True))

        for name in self._NAME_FIELDS:
            non_latin = getattr(self, f"{name}NonLatin")
            self._subelement(
                root,
                "sdg",
                name,
                text=getattr(self, name),
                attrib={"nonLatin": non_latin} if non_latin else None,
            )

        self._subelement(root, "sdg", "DateOfBirth", text=self.DateOfBirth)

        for tag in self._TEXT_FIELDS:
            self._subelement(root, "sdg", tag, text=getattr(self, tag))

        self._xml = root
        return root

    def get_xml(self) -> str:
        return super().get_xml()

    def get_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for name, _ in self._FIELD_ALIASES:
            if name == "identifier":
                data[name] = (
                    {
                        "value": self.identifier.value,
                        "schemeID": self.identifier.schemeID,
                    }
                    if self.identifier is not None
                    else None
                )
            else:
                data[name] = self._serialize_value(getattr(self, name))
        return data

    @classmethod
    def set_from_dict(cls, data: dict[str, Any]) -> "Person":
        if not isinstance(data, dict):
            raise TypeError(f"Очікувався dict, отримано {type(data).__name__}")

        identifier_data = data.get("identifier")
        identifier: Identifier | None
        if isinstance(identifier_data, Identifier):
            identifier = identifier_data
        elif isinstance(identifier_data, dict):
            identifier = Identifier(
                identifier_data.get("value"),
                identifier_data.get("schemeID", "eidas"),
            )
        elif isinstance(identifier_data, str):
            identifier = Identifier(identifier_data)
        else:
            legacy_identifier = data.get("eidas_identifier")
            identifier = Identifier(value=legacy_identifier) if legacy_identifier is not None else None

        person = cls(identifier=identifier)
        for name, alias in cls._FIELD_ALIASES:
            if name == "identifier":
                continue
            setattr(person, name, data.get(name, data.get(alias)))

        person.LevelOfAssurance = str(person.LevelOfAssurance or "High")
        person.DateOfBirth = cls._parse_date(person.DateOfBirth)
        return person

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Person":
        return cls.set_from_dict(data)


    @property
    def dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for name, alias in self._FIELD_ALIASES:
            if name == "identifier":
                data[alias] = self.identifier.value if self.identifier else None
            else:
                data[alias] = self._serialize_value(getattr(self, name))
        return data

    @dict.setter
    def dict(self, d: Any) -> None:
        person = self.set_from_dict(d)
        for name, _ in self._FIELD_ALIASES:
            setattr(self, name, getattr(person, name))

    async def from_redis(self, redis, key):
        person = await get_person_from_redis(redis, key)
        if person is not None:
            self.dict = person.dict


async def save_person_to_redis(redis_client, key: str, person: Person) -> None:
    """
    Зберігає Person до Redis як JSON через властивість dict.

    Args:
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для збереження
        person: Об'єкт Person
    """
    await save_model_to_redis(
        redis_client,
        key,
        person,
        Person,
        to_dict=lambda p: p.dict,
    )


async def get_person_from_redis(redis_client, key: str) -> Person | None:
    """
    Отримує Person з Redis і десеріалізує у модель.

    Args:
        redis_client: Екземпляр UseRedisAsync
        key: Ключ Redis для читання

    Returns:
        Person або None, якщо ключ відсутній
    """
    return await load_model_from_redis(redis_client, key, "Person", _dict_to_person)


def _dict_to_person(data: dict) -> Person:
    """Конвертує словник у Person."""
    person = Person()
    person.dict = data
    return person
