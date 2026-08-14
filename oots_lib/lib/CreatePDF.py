import logging
import pathlib
import re
from collections.abc import Iterable

from lxml import etree

from oots_lib.lib.xml_safety import safe_fromstring, safe_parse

try:
    from weasyprint import CSS, HTML  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    CSS = None
    HTML = None


_logger = logging.getLogger(__name__)

path = pathlib.Path(__file__).parent
XSLT_FILE = path / "rdf-display.xsl"
BIRTH_CERTIFICATE_XSLT_FILE = path / "annexI_birth.xsl"
MARRIAGE_CERTIFICATE_XSLT_FILE = path / "annexIV_marriage.xsl"
DISABILITY_CERTIFICATE_XSLT_FILE = path / "disability.xsl"


def generate_pdf_from_xslt(
    rdf: str | bytes,
    xslt_file: pathlib.Path | str = XSLT_FILE,
    css: Iterable[str] | None = None,
) -> bytes:
    """
    Виконує XSLT-трансформацію XML у HTML, а потім перетворює HTML у PDF.
    """
    if HTML is None or CSS is None:
        raise ModuleNotFoundError(
            "weasyprint is required for PDF generation. Install the optional dependency to use generate_pdf_from_xslt()."
        )

    # Крок 1: Завантаження та виконання XSLT-трансформації

    # Конвертація xslt_file у pathlib.Path якщо потрібно
    if isinstance(xslt_file, str):
        xslt_file = pathlib.Path(xslt_file)

    # Завантаження XML-документа
    if isinstance(rdf, bytes):
        rdf = rdf.decode("utf-8")

    xml = re.sub(r"<\?xml [^>]*\?>\s*", '', rdf, count=1)
    xml = xml.strip()
    xml_tree = safe_fromstring(xml)

    # Завантаження XSLT-таблиці стилів
    xslt_root = safe_parse(xslt_file)
    transform = etree.XSLT(
        xslt_root,
        access_control=etree.XSLTAccessControl.DENY_ALL,  # type: ignore[attr-defined]
    )

    # Виконання трансформації: XML -> HTML (як etree.ElementTree)
    html_tree = transform(xml_tree)

    # Серіалізація HTML у рядок
    html_content = etree.tostring(
        html_tree,
        pretty_print=True,
        method="html",
        encoding='utf-8'
    ).decode('utf-8')

    # Крок 2: Перетворення HTML у PDF за допомогою WeasyPrint

    html_object = HTML(string=html_content)

    stylesheets = [CSS(string='@page { size: A4; margin: 1.5cm; }')]
    for c in (css or []):
        stylesheets.append(CSS(string=c))

    # Виклик write_pdf() без аргументу target повертає PDF як bytes.
    pdf_bytes: bytes = html_object.write_pdf(stylesheets=stylesheets)  # type: ignore[assignment]

    return pdf_bytes
