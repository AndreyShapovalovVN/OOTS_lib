"""Public API for the OOTS evidence library."""

from importlib import import_module

__all__ = [
    "Base",
    "MainBase",
    "NS",
    "SOAPTransport",
    "EDMException",
    "BaseEDMException",
    "TransportError",
    "ReportingError",
    "LoggerServiceError",
    "RedisDataError",
    "AuthenticationException",
    "AuthorizationException",
    "InvalidRequestException",
    "ObjectNotFoundException",
    "QueryException",
    "TimeoutException",
    "UnresolvedReferenceException",
    "UnsupportedCapabilityException",
    "MakeEvidence",
    "UseRedisAsync",
    "get_redis_client",
    "initialize_redis",
    "close_redis",
    "generate_pdf_from_xslt",
    "Identifier",
    "Person",
    "EDMRequest",
    "Evidences",
    "Description",
    "Classification",
    "RepositoryItemRef",
    "ExtrinsicObjectType",
    "RegistryPackageType",
]

_LAZY_IMPORTS = {
    "Base": ("oots_lib.models.Base", "Base"),
    "MainBase": ("oots_lib.models.Base", "MainBase"),
    "NS": ("oots_lib.lib.NS", "NS"),
    "SOAPTransport": ("oots_lib.Transport", "SOAPTransport"),
    "EDMException": ("oots_lib.lib.exception", "EDMException"),
    "BaseEDMException": ("oots_lib.lib.exceptions", "EDMException"),
    "TransportError": ("oots_lib.lib.exception", "TransportError"),
    "ReportingError": ("oots_lib.lib.exception", "ReportingError"),
    "LoggerServiceError": ("oots_lib.lib.toLogger", "LoggerServiceError"),
    "RedisDataError": ("oots_lib.lib.UseRedis", "RedisDataError"),
    "AuthenticationException": ("oots_lib.lib.exceptions", "AuthenticationException"),
    "AuthorizationException": ("oots_lib.lib.exceptions", "AuthorizationException"),
    "InvalidRequestException": ("oots_lib.lib.exceptions", "InvalidRequestException"),
    "ObjectNotFoundException": ("oots_lib.lib.exceptions", "ObjectNotFoundException"),
    "QueryException": ("oots_lib.lib.exceptions", "QueryException"),
    "TimeoutException": ("oots_lib.lib.exceptions", "TimeoutException"),
    "UnresolvedReferenceException": ("oots_lib.lib.exceptions", "UnresolvedReferenceException"),
    "UnsupportedCapabilityException": ("oots_lib.lib.exceptions", "UnsupportedCapabilityException"),
    "MakeEvidence": ("oots_lib.lib.MakeEvidence", "MakeEvidence"),
    "UseRedisAsync": ("oots_lib.lib.UseRedis", "UseRedisAsync"),
    "get_redis_client": ("oots_lib.lib.UseRedis", "get_redis_client"),
    "initialize_redis": ("oots_lib.lib.UseRedis", "initialize_redis"),
    "close_redis": ("oots_lib.lib.UseRedis", "close_redis"),
    "generate_pdf_from_xslt": ("oots_lib.lib.CreatePDF", "generate_pdf_from_xslt"),
    "Identifier": ("oots_lib.models.Person", "Identifier"),
    "Person": ("oots_lib.models.Person", "Person"),
    "EDMRequest": ("oots_lib.models.RequestEDM", "EDMRequest"),
    "Evidences": ("oots_lib.models.ResponseEvidences", "Evidences"),
    "Description": ("oots_lib.models.ResponseEvidences", "Description"),
    "Classification": ("oots_lib.models.ResponseEvidences", "Classification"),
    "RepositoryItemRef": ("oots_lib.models.ResponseEvidences", "RepositoryItemRef"),
    "ExtrinsicObjectType": ("oots_lib.models.ResponseEvidences", "ExtrinsicObjectType"),
    "RegistryPackageType": ("oots_lib.models.ResponseEvidences", "RegistryPackageType"),
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
