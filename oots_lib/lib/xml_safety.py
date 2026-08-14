"""Hardened XML parsing helpers.

Untrusted XML (evidence payloads, person data received from Redis or SOAP)
must never be parsed with lxml defaults, which resolve entities and allow
DTD loading — that exposes local file disclosure (XXE) and entity-expansion
denial of service.
"""

import pathlib

from lxml import etree

__all__ = ["safe_fromstring", "safe_parse", "safe_parser"]


def safe_parser() -> etree.XMLParser:
    """Parser with entity resolution, DTD loading and network access disabled."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )


def safe_fromstring(xml: str | bytes) -> etree._Element:
    """Parses an XML string/bytes, rejecting documents that declare a DTD."""
    root = etree.fromstring(xml, parser=safe_parser())
    _reject_doctype(root)
    return root


def safe_parse(source: pathlib.Path | str) -> etree._ElementTree:
    """Parses an XML file, rejecting documents that declare a DTD."""
    tree = etree.parse(str(source), parser=safe_parser())
    _reject_doctype(tree.getroot())
    return tree


def _reject_doctype(root: etree._Element) -> None:
    tree = root.getroottree()
    if tree.docinfo.internalDTD is not None or tree.docinfo.externalDTD is not None:
        raise ValueError("XML з DOCTYPE/DTD не приймається")
