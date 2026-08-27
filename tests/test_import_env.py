import pytest

from oots_lib.import_env import import_env


def test_returns_env_value(monkeypatch):
    assert import_env("COUNTRY") == "UA"


def test_returns_default_when_missing(monkeypatch):
    assert import_env("REDIS_PREFIX", "fallback") == "fallback"


def test_env_value_wins_over_default(monkeypatch):
    assert import_env("SOME_TEST_VAR", "fallback") == "value"


def test_raises_without_value_and_default(monkeypatch):
    with pytest.raises(ValueError, match="MISSING_TEST_VAR"):
        import_env("MISSING_TEST_VAR")
