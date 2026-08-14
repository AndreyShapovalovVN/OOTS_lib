import pytest

from oots_lib.import_env import import_env


def test_returns_env_value(monkeypatch):
    monkeypatch.setenv("SOME_TEST_VAR", "value")
    assert import_env("SOME_TEST_VAR") == "value"


def test_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("MISSING_TEST_VAR", raising=False)
    assert import_env("MISSING_TEST_VAR", "fallback") == "fallback"


def test_env_value_wins_over_default(monkeypatch):
    monkeypatch.setenv("SOME_TEST_VAR", "value")
    assert import_env("SOME_TEST_VAR", "fallback") == "value"


def test_raises_without_value_and_default(monkeypatch):
    monkeypatch.delenv("MISSING_TEST_VAR", raising=False)
    with pytest.raises(ValueError, match="MISSING_TEST_VAR"):
        import_env("MISSING_TEST_VAR")
