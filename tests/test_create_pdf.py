import pytest

import oots_lib.lib.CreatePDF as create_pdf
from oots_lib.lib.CreatePDF import generate_pdf_from_xslt

XSLT = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/doc">
    <html><body><p><xsl:value-of select="title"/></p></body></html>
  </xsl:template>
</xsl:stylesheet>
"""

RDF = '<?xml version="1.0" encoding="UTF-8"?>\n<doc><title>Свідоцтво</title></doc>'


class FakeCSS:
    def __init__(self, string: str):
        self.string = string


class FakeHTML:
    instances: list["FakeHTML"] = []

    def __init__(self, string: str):
        self.string = string
        self.stylesheets: list[FakeCSS] | None = None
        FakeHTML.instances.append(self)

    def write_pdf(self, stylesheets=None):
        self.stylesheets = stylesheets
        return b"%PDF-fake"


@pytest.fixture
def xslt_file(tmp_path):
    path = tmp_path / "display.xsl"
    path.write_text(XSLT, encoding="utf-8")
    return path


@pytest.fixture
def fake_weasyprint(monkeypatch):
    FakeHTML.instances.clear()
    monkeypatch.setattr(create_pdf, "HTML", FakeHTML)
    monkeypatch.setattr(create_pdf, "CSS", FakeCSS)
    return FakeHTML


def test_default_xslt_paths_point_into_package():
    assert create_pdf.XSLT_FILE.name == "rdf-display.xsl"
    assert create_pdf.XSLT_FILE.parent == create_pdf.path
    assert create_pdf.BIRTH_CERTIFICATE_XSLT_FILE.name == "annexI_birth.xsl"
    assert create_pdf.MARRIAGE_CERTIFICATE_XSLT_FILE.name == "annexIV_marriage.xsl"
    assert create_pdf.DISABILITY_CERTIFICATE_XSLT_FILE.name == "disability.xsl"


@pytest.mark.parametrize("missing", ["HTML", "CSS"])
def test_raises_without_weasyprint(monkeypatch, xslt_file, missing):
    monkeypatch.setattr(create_pdf, "HTML", FakeHTML)
    monkeypatch.setattr(create_pdf, "CSS", FakeCSS)
    monkeypatch.setattr(create_pdf, missing, None)

    with pytest.raises(ModuleNotFoundError, match="weasyprint"):
        generate_pdf_from_xslt(RDF, xslt_file)


def test_transforms_xml_and_returns_pdf_bytes(fake_weasyprint, xslt_file):
    assert generate_pdf_from_xslt(RDF, xslt_file) == b"%PDF-fake"

    html = fake_weasyprint.instances[-1]
    assert "<p>Свідоцтво</p>" in html.string


def test_accepts_bytes_and_str_paths(fake_weasyprint, xslt_file):
    assert generate_pdf_from_xslt(RDF.encode("utf-8"), str(xslt_file)) == b"%PDF-fake"
    assert "<p>Свідоцтво</p>" in fake_weasyprint.instances[-1].string


def test_default_page_stylesheet_is_always_applied(fake_weasyprint, xslt_file):
    generate_pdf_from_xslt(RDF, xslt_file)

    stylesheets = fake_weasyprint.instances[-1].stylesheets
    assert stylesheets is not None
    assert [css.string for css in stylesheets] == ["@page { size: A4; margin: 1.5cm; }"]


def test_extra_css_is_appended(fake_weasyprint, xslt_file):
    generate_pdf_from_xslt(RDF, xslt_file, css=["p { color: red; }", "p { margin: 0; }"])

    stylesheets = fake_weasyprint.instances[-1].stylesheets
    assert [css.string for css in stylesheets][1:] == [
        "p { color: red; }",
        "p { margin: 0; }",
    ]


def test_invalid_xml_raises(fake_weasyprint, xslt_file):
    from lxml import etree

    with pytest.raises(etree.XMLSyntaxError):
        generate_pdf_from_xslt("<doc><title>broken", xslt_file)


def test_missing_xslt_file_raises(fake_weasyprint, tmp_path):
    from lxml import etree

    with pytest.raises((OSError, etree.XMLSyntaxError)):
        generate_pdf_from_xslt(RDF, tmp_path / "missing.xsl")
