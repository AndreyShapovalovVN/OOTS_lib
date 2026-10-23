import copy
import datetime
import json
import pathlib
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field, is_dataclass
from typing import ClassVar

from lxml import etree

from oots_lib.lib.CreatePDF import generate_pdf_from_xslt
from oots_lib.lib.xml_utils import set_element_text


@dataclass
class Base(ABC):
    serialization_fields: ClassVar[tuple[str, ...]] = ()

    def _serialization_items(self):
        """Повертає лише явно дозволені поля у заданому порядку."""
        for name in self.serialization_fields:
            if name.startswith("_"):
                raise ValueError(f"Службове поле не можна серіалізувати: {name}")
            yield name, getattr(self, name)

    @staticmethod
    def _dict_value(value):
        if isinstance(value, Base):
            return value.get_dict()
        if is_dataclass(value) and not isinstance(value, type):
            raise TypeError("Вкладена модель має успадковувати Base та визначати serialization_fields")
        if isinstance(value, dict):
            return {key: Base._dict_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(Base._dict_value(item) for item in value)
        return copy.deepcopy(value)

    def get_dict(self) -> dict:
        return {name: self._dict_value(value) for name, value in self._serialization_items()}

    @staticmethod
    def _append_xml_value(root: etree._Element, name: str, value) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                Base._append_xml_value(root, name, item)
        elif isinstance(value, Base):
            element = copy.deepcopy(value.get_element())
            element.tag = name
            root.append(element)
        elif isinstance(value, dict):
            element = etree.SubElement(root, name)
            for key, item in value.items():
                Base._append_xml_value(element, key, item)
        elif is_dataclass(value) and not isinstance(value, type):
            raise TypeError("Вкладена модель має успадковувати Base та визначати serialization_fields")
        else:
            Base._set_text(etree.SubElement(root, name), value)

    @staticmethod
    def _set_text(element: etree._Element, value) -> None:
        set_element_text(element, value)

    @staticmethod
    def _parse_date(value) -> datetime.date | None:
        if value in (None, "", {}):
            return None
        if isinstance(value, datetime.date):
            return value
        return datetime.date.fromisoformat(str(value))

    @staticmethod
    def _parse_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() == "true"

    @abstractmethod
    def get_element(self) -> etree._Element:
        pass


@dataclass
class MainBase(Base):
    _name_: str | None = field(default=None, kw_only=True)

    def get_element(self) -> etree._Element:
        """Стандартний XML; спеціальні схеми можуть перевизначити цей метод."""
        root = etree.Element(type(self).__name__)
        for name, value in self._serialization_items():
            self._append_xml_value(root, name, value)
        return root

    @classmethod
    def set_from_dict(cls, data: dict):
        raise NotImplementedError(
            "Метод set_from_dict должен быть реализован в подклассе"
        )

    def get_xml(self) -> str:
        xml_bytes: bytes = etree.tostring(
            self.get_element(),
            pretty_print=True,
            encoding="utf-8",
        )
        return xml_bytes.decode("utf-8")

    def get_json(self) -> str:
        data = self.get_dict()
        if self._name_:
            data = {self._name_: data}
        return json.dumps(data, default=str, ensure_ascii=False)

    def get_pdf(
        self,
        xslt_file: str | pathlib.Path,
        css: Iterable[str] | None = None,
    ) -> bytes:
        """Генерує PDF з XML-представлення моделі."""
        return generate_pdf_from_xslt(
            rdf=self.get_xml(),
            xslt_file=xslt_file,
            css=css,
        )
