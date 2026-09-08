import datetime
import json
import pathlib
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

from lxml import etree

from oots_lib.lib.CreatePDF import generate_pdf_from_xslt
from oots_lib.lib.xml_utils import set_element_text


@dataclass
class Base(ABC):

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

    def get_dict(self) -> dict:
        data = asdict(self)
        data.pop("_name_", None)
        return data

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
