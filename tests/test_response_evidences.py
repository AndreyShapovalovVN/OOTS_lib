from dataclasses import asdict

import pytest

from oots_lib.models.ResponseEvidences import (
    Classification,
    Description,
    Evidences,
    ExtrinsicObjectType,
    RegistryPackageType,
    RepositoryItemRef,
    _generate_cid,
    _generate_identifier,
    _is_legacy_evidences_dict,
    _normalize_legacy_evidences_dict,
    get_evidences_from_redis,
    get_legacy_evidences_from_redis,
    save_evidences_to_redis,
    to_legacy_evidences_dict,
)


class RedisStub:
    def __init__(self, value=None):
        self.value = value
        self.saved: list[tuple[str, object]] = []

    async def save_to_redis(self, key, value):
        self.saved.append((key, value))
        self.value = value

    async def get_from_redis(self, key):
        return self.value


def make_object(node: str = "MainEvidence", content: str = "<a/>") -> ExtrinsicObjectType:
    return ExtrinsicObjectType(
        classification=Classification(classificationNode=node),
        EvidenceMetadata="<sdg:Evidence/>",
        RepositoryItemRef=RepositoryItemRef(title="Certificate"),
        content_type="application/xml",
        content=content,
    )


def make_evidences(*objects: ExtrinsicObjectType, permit: bool = True) -> Evidences:
    return Evidences(
        title="Свідоцтво",
        PreviewDescription=[Description(lang="UA", value="Опис")],
        preview=True,
        evidences=[RegistryPackageType(RegistryPackage=list(objects) or [make_object()], permit=permit)],
    )


def test_generated_identifiers_are_unique_and_prefixed():
    assert _generate_cid().startswith("cid:")
    assert _generate_cid().endswith("@gov.ua")
    assert _generate_cid() != _generate_cid()
    assert _generate_identifier().startswith("urn:uuid:")
    assert _generate_identifier() != _generate_identifier()


def test_classification_defaults():
    classification = Classification(classificationNode="Annex")
    assert classification.classificationScheme == "urn:fdc:oots:classification:edm"
    assert classification.id.startswith("urn:uuid:")


def test_classification_rejects_unknown_node():
    with pytest.raises(ValueError, match="Некоректне classificationNode"):
        Classification(classificationNode="Unknown")


def test_repository_item_ref_generates_href():
    assert RepositoryItemRef(title="t").href.startswith("cid:")
    assert RepositoryItemRef(title="t", href="cid:custom").href == "cid:custom"


async def test_save_rejects_wrong_type():
    with pytest.raises(TypeError, match="Evidences"):
        await save_evidences_to_redis(RedisStub(), "key", {"title": "x"})  # type: ignore[arg-type]


async def test_roundtrip_through_redis_preserves_structure():
    redis = RedisStub()
    original = make_evidences(make_object(), make_object(node="HumanReadableVersion"))

    await save_evidences_to_redis(redis, "key", original)
    restored = await get_evidences_from_redis(redis, "key")

    assert restored == original
    assert redis.saved[0][0] == "key"


async def test_get_returns_none_when_key_missing():
    assert await get_evidences_from_redis(RedisStub(None), "key") is None


async def test_get_raises_on_broken_payload():
    with pytest.raises(ValueError, match="десеріалізувати"):
        await get_evidences_from_redis(RedisStub({"PreviewDescription": []}), "key")


def test_to_legacy_dict_keeps_only_main_evidence():
    evidences = make_evidences(
        make_object(content="<main/>"),
        make_object(node="Translation", content="<translated/>"),
    )

    legacy = to_legacy_evidences_dict(evidences)

    assert legacy["title"] == "Свідоцтво"
    assert legacy["PreviewDescription"] == [{"UA": "Опис"}]
    assert legacy["preview"] is True
    assert legacy["exaption"] == ""
    assert len(legacy["evidences"]) == 1
    assert legacy["evidences"][0]["content"] == "<main/>"
    assert legacy["evidences"][0]["permit"] is True
    assert legacy["evidences"][0]["content_type"] == "application/xml"
    assert legacy["evidences"][0]["metadata"] == "<sdg:Evidence/>"
    assert legacy["evidences"][0]["cid"].startswith("cid:")


def test_to_legacy_dict_rejects_wrong_type():
    with pytest.raises(TypeError, match="Evidences"):
        to_legacy_evidences_dict({"title": "x"})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("not-a-dict", False),
        ({"title": "x"}, False),
        ({"evidences": "not-a-list"}, False),
        ({"evidences": []}, False),
        ({"evidences": [], "exaption": ""}, True),
        ({"evidences": [{"cid": "cid:1"}]}, True),
        ({"evidences": [{"RegistryPackage": []}]}, False),
    ],
)
def test_is_legacy_evidences_dict(data, expected):
    assert _is_legacy_evidences_dict(data) is expected


def test_normalize_legacy_dict_fills_defaults():
    assert _normalize_legacy_evidences_dict({"evidences": [{"cid": "cid:1"}]}) == {
        "title": "",
        "PreviewDescription": [],
        "preview": True,
        "exaption": "",
        "evidences": [{"cid": "cid:1"}],
    }


async def test_get_legacy_from_redis_converts_new_format():
    redis = RedisStub(asdict(make_evidences()))

    legacy = await get_legacy_evidences_from_redis(redis, "key")

    assert legacy is not None
    assert legacy["title"] == "Свідоцтво"
    assert len(legacy["evidences"]) == 1


async def test_get_legacy_from_redis_passes_through_legacy_format():
    payload = {"title": "old", "evidences": [{"cid": "cid:1"}], "exaption": ""}

    assert await get_legacy_evidences_from_redis(RedisStub(payload), "key") == {
        "title": "old",
        "PreviewDescription": [],
        "preview": True,
        "exaption": "",
        "evidences": [{"cid": "cid:1"}],
    }


async def test_get_legacy_from_redis_returns_none_when_missing():
    assert await get_legacy_evidences_from_redis(RedisStub(None), "key") is None
