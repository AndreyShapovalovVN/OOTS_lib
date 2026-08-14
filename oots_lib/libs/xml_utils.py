"""Спільні помічники для побудови XML-елементів."""

import datetime
from typing import Any

__all__ = [
    "clean_attrib",
    "coerce_text",
    "set_element_text",
]


def coerce_text(value: Any) -> str | None:
    """Приводить значення до тексту XML-елемента, `None` залишає `None`."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def set_element_text(element: Any, value: Any) -> None:
    """Записує значення у текст елемента, пропускаючи `None`."""
    text = coerce_text(value)
    if text is not None:
        element.text = text


def clean_attrib(attrib: dict[Any, Any]) -> dict[Any, str]:
    """Викидає `None` і приводить значення атрибутів до рядків."""
    cleaned: dict[Any, str] = {}
    for name, value in attrib.items():
        text = coerce_text(value)
        if text is not None:
            cleaned[name] = text
    return cleaned
