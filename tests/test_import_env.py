import pytest

from oots_lib.import_env import import_env


def test_returns_env_value(monkeypatch):
    assert import_env("COUNTRY") == "UA"


def test_returns_default_when_missing(monkeypatch):
    assert import_env("REDIS_PREFIX", "fallback") == "fallback"

