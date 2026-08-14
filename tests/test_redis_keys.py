import pytest

from oots_lib.redis_keys import Keys

CONVERSATION_ID = "abc-123"

KEYS = Keys()


@pytest.mark.parametrize(
    ("method_name", "expected"),
    [
        ("get_response_evidence", "oots:message:response:evidence:abc-123"),
        ("get_response_permit", "oots:message:request:permit:abc-123"),
        ("get_response_edm", "oots:message:response:edm:abc-123"),
        ("get_response_exp", "oots:message:response:exp:abc-123"),
        ("get_request_person", "oots:message:request:person:abc-123"),
        ("get_request_edm", "oots:message:request:edm:abc-123"),
        ("get_request_as4", "oots:message:request:as4:abc-123"),
        ("get_request_preview", "oots:message:request:preview:abc-123"),
    ],
)
def test_conversation_keys(method_name, expected):
    assert getattr(KEYS, method_name)(CONVERSATION_ID) == expected


def test_evidence_type_key():
    assert KEYS.get_evidence_type("type-1") == "oots:evidencetype:type-1"


def test_templates_are_overridable_per_instance():
    keys = Keys(RESPONSE_EDM="custom:{conversation_id}")
    assert keys.get_response_edm(CONVERSATION_ID) == "custom:abc-123"
    assert Keys().get_response_edm(CONVERSATION_ID) == "oots:message:response:edm:abc-123"
