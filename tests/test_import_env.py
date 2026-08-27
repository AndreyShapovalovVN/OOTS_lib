import pytest

from oots_lib.import_env import import_env


def test_returns_env_value(monkeypatch):
    assert import_env("COUNTRY") == "UA"


def test_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("REDIS_PREFIX", raising=False)
    assert import_env("REDIS_PREFIX", "fallback") == "fallback"


def test_raises_when_environment_variable_is_missing(monkeypatch):
    monkeypatch.delenv("IS_TEST", raising=False)
    monkeypatch.delenv("NON_EXISTENT_VARIABLE", raising=False)

    with pytest.raises(ValueError, match="NON_EXISTENT_VARIABLE"):
        import_env("NON_EXISTENT_VARIABLE")
