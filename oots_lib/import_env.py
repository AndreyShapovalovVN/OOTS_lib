import logging
import os

_logger = logging.getLogger(__name__)


def import_env(key: str, default: str | None = None) -> str:
    is_test = os.getenv("IS_TEST") == "true"
    if is_test:
        default = default or ""

    value = os.getenv(key, default)

    if value is None:
        _logger.error("Environment variable %s is not set", key)
        raise ValueError(f"Environment variable {key} is not set")
    return value
