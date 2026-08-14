import base64
from typing import Any, cast

import pytest
from lxml import etree

import oots_lib.lib.MakeEvidence as make_evidence_module
from oots_lib.lib.exception import EDMException
from oots_lib.lib.MakeEvidence import KEYS, MakeEvidence
from oots_lib.models.Person import Person
from oots_lib.models.RequestEDM import EDMRequest
from oots_lib.models.ResponseEvidences import Evidences


class RedisSpy:
    def __init__(self, storage: dict | None = None):
        self.storage = storage or {}
        self.saved: dict = {}
        self.pushed: list[tuple[str, str]] = []

    async def get_from_redis(self, key):
        return self.storage.get(key)

    async def save_to_redis(self, key, value):
        self.saved[key] = value

    async def push_to_queue(self, queue, message):
        self.pushed.append((queue, message))


class FakeParsing:
    """Двійник `pyRegRep4.RIMParsing.Parsing` з керованим вмістом запиту."""

    def __init__(self, content, preview: bool = False, content_type: str = "application/xml"):
        self.content = content
        self.preview = preview
        self.content_type = content_type

    def serialize(self, any_type: bool = False):
        if any_type:
            return {
                "query": {
                    "EvidenceRequest": {
                        "sdg:DataServiceEvidenceType": {
                            "sdg:DistributedAs": {"sdg:Format": self.content_type}
                        }
                    }
                }
            }
        return {"doc": {"PossibilityForPreview": self.preview}}


class FakeDocument:
    def get_xml(self):
        return "<doc/>"

    def get_json(self):
        return '{"doc": true}'

    def get_pdf(self):
        return b"%PDF"


class Evidence(MakeEvidence):
    ISSUING_AUTHORITY_ID = "42"
    ISSUING_AUTHORITY_SCHEME = "urn:scheme"
    ISSUING_AUTHORITY_NAME = "ДРАЦС"
    CONFORMANT_TO_URL = "urn:conformance"


class FakeData:
    def __init__(self, documents=None, error: Exception | None = None):
        self.documents = documents if documents is not None else [FakeDocument()]
        self.error = error

    async def generate_data(self):
        if self.error is not None:
            raise self.error
        return self.documents


def make_person() -> Person:
    person = Person(FamilyName="Shevchenko", GivenName="Taras")
    person.get_element()
    return person


def build(redis: RedisSpy, content_type: str = "application/xml", preview: bool = False) -> Evidence:
    evidence = Evidence("msg-1", cast("Any", redis))
    evidence.request = FakeParsing("<query/>", preview=preview, content_type=content_type)
    evidence.person = make_person()
    evidence.title = "Свідоцтво"
    evidence.data = cast("Any", FakeData())
    return evidence


def test_initial_state():
    redis = RedisSpy()
    evidence = Evidence("msg-1", redis)

    assert evidence.message_id == "msg-1"
    assert evidence.redis is redis
    assert evidence.person is None
    assert evidence.request is None
    assert evidence.evidence is None
    assert evidence.title == ""
    assert evidence.description == []


@pytest.mark.parametrize(
    ("request_preview", "global_preview", "expected"),
    [(False, False, False), (True, False, True), (False, True, True), (True, True, True)],
)
def test_if_preview_combines_request_and_global_flag(
    monkeypatch, request_preview, global_preview, expected
):
    monkeypatch.setattr(make_evidence_module, "IF_PREVIEW", global_preview)
    evidence = build(RedisSpy(), preview=request_preview)

    assert evidence.if_preview is expected


def test_request_content_type_is_cached():
    evidence = build(RedisSpy(), content_type="application/pdf")

    assert evidence.request_content_type == "application/pdf"
    evidence.request.content_type = "application/json"
    assert evidence.request_content_type == "application/pdf"


def test_request_content_type_requires_request():
    with pytest.raises(ValueError, match="Запит не ініціалізовано"):
        _ = Evidence("msg-1", RedisSpy()).request_content_type


async def test_read_data_loads_request_person_and_as4(monkeypatch):
    person = make_person()
    redis = RedisSpy(
        {
            KEYS.get_request_edm("msg-1"): {
                "href": "cid:1@gov.ua",
                "MimeType": "application/xml",
                "content": "<query/>",
            },
            KEYS.get_request_person("msg-1"): person.dict,
            KEYS.get_request_as4("msg-1"): {"messageId": "as4-1"},
        }
    )
    monkeypatch.setattr(make_evidence_module, "Parsing", FakeParsing)

    evidence = Evidence("msg-1", redis)
    await evidence.read_data()

    assert isinstance(evidence.request, FakeParsing)
    assert evidence.request.content == "<query/>"
    assert evidence.person is not None
    assert evidence.person.FamilyName == "Shevchenko"
    assert evidence.as4 == {"messageId": "as4-1"}


async def test_read_data_uses_edm_request_content(monkeypatch):
    captured = {}

    def parsing(content):
        captured["content"] = content
        return FakeParsing(content)

    monkeypatch.setattr(make_evidence_module, "Parsing", parsing)
    monkeypatch.setattr(
        make_evidence_module,
        "get_edm_request_from_redis",
        lambda redis, key: _async_value(
            EDMRequest(href="cid:1@gov.ua", MimeType="application/xml", content="<q/>")
        ),
    )

    await Evidence("msg-1", RedisSpy()).read_data()

    assert captured["content"] == "<q/>"


async def _async_value(value):
    return value


def test_generate_metadata_contains_all_sections():
    xml = build(RedisSpy()).generate_metadata()

    assert "sdg:IsAbout" in xml
    assert "sdg:IsConformantTo" in xml
    assert "sdg:Distribution" in xml
    assert "sdg:IssuingAuthority" in xml

    root = etree.fromstring(xml.encode("utf-8"))
    name = root.find(".//{http://data.europa.eu/p4s}Name")
    assert name is not None
    assert name.text == "ДРАЦС"


def test_generate_metadata_skips_sections_for_secondary_evidence():
    xml = build(RedisSpy()).generate_metadata(main_evidence=False)

    assert "sdg:IsAbout" not in xml
    assert "sdg:Identifier" in xml


def test_generate_metadata_requires_person():
    evidence = build(RedisSpy())
    evidence.person = None

    with pytest.raises(AssertionError, match="person must be set"):
        evidence.generate_metadata()


@pytest.mark.parametrize(
    ("content_type", "expected_type"),
    [
        ("application/xml", "application/xml"),
        ("application/json", "application/json"),
    ],
)
async def test_transform_data_builds_text_representations(content_type, expected_type):
    evidence = build(RedisSpy(), content_type=content_type)

    await evidence.transform_data()

    assert isinstance(evidence.evidence, Evidences)
    assert evidence.evidence.title == "Свідоцтво"
    assert len(evidence.evidence.evidences) == 1
    extrinsic = evidence.evidence.evidences[0].RegistryPackage[0]
    assert extrinsic.content_type == expected_type
    assert extrinsic.classification.classificationNode == "MainEvidence"
    assert extrinsic.encoding is None
    assert "sdg:Evidence" in extrinsic.EvidenceMetadata


async def test_transform_data_encodes_pdf_as_base64():
    evidence = build(RedisSpy(), content_type="application/pdf")

    await evidence.transform_data()

    extrinsic = evidence.evidence.evidences[0].RegistryPackage[0]
    assert extrinsic.encoding == "base64"
    assert base64.b64decode(extrinsic.content) == b"%PDF"


async def test_transform_data_handles_several_documents():
    evidence = build(RedisSpy())
    evidence.data = FakeData([FakeDocument(), FakeDocument()])

    await evidence.transform_data()

    assert len(evidence.evidence.evidences) == 2


async def test_transform_data_raises_edm_exception_for_unknown_content_type():
    evidence = build(RedisSpy(), content_type="application/msword")

    with pytest.raises(EDMException, match="EDM:ERR:0006"):
        await evidence.transform_data()


async def test_transform_data_wraps_data_errors():
    evidence = build(RedisSpy())
    evidence.data = FakeData(error=RuntimeError("нема даних"))

    with pytest.raises(EDMException, match="EDM:ERR:0004"):
        await evidence.transform_data()


async def test_load_data_to_redis_pushes_to_queue_without_preview():
    redis = RedisSpy()
    evidence = build(redis)
    await evidence.transform_data()

    await evidence.load_data_to_redis()

    assert KEYS.get_response_evidence("msg-1") in redis.saved
    assert redis.pushed == [(make_evidence_module.QUEUE_OUTCOMING, "msg-1")]


async def test_load_data_to_redis_skips_queue_when_preview_required():
    redis = RedisSpy()
    evidence = build(redis, preview=True)
    await evidence.transform_data()

    await evidence.load_data_to_redis()

    assert KEYS.get_response_evidence("msg-1") in redis.saved
    assert redis.pushed == []


async def test_load_data_to_redis_requires_dataclass_evidence():
    evidence = build(RedisSpy())
    evidence.evidence = "not-a-dataclass"  # type: ignore[assignment]

    with pytest.raises(TypeError, match="Evidences"):
        await evidence.load_data_to_redis()
