"""Models used by the OOTS evidence library."""

from importlib import import_module

__all__ = [
    "Base",
    "MainBase",
    "Identifier",
    "Person",
    "EDMRequest",
    "Evidences",
    "Description",
    "Classification",
    "RepositoryItemRef",
    "ExtrinsicObjectType",
    "RegistryPackageType",
    "save_edm_request_to_redis",
    "get_edm_request_from_redis",
    "save_evidences_to_redis",
    "get_evidences_from_redis",
    "to_legacy_evidences_dict",
]

_LAZY_IMPORTS = {
    "Base": ("oots_lib.models.Base", "Base"),
    "MainBase": ("oots_lib.models.Base", "MainBase"),
    "Identifier": ("oots_lib.models.Person", "Identifier"),
    "Person": ("oots_lib.models.Person", "Person"),
    "EDMRequest": ("oots_lib.models.RequestEDM", "EDMRequest"),
    "Evidences": ("oots_lib.models.ResponseEvidences", "Evidences"),
    "Description": ("oots_lib.models.ResponseEvidences", "Description"),
    "Classification": ("oots_lib.models.ResponseEvidences", "Classification"),
    "RepositoryItemRef": ("oots_lib.models.ResponseEvidences", "RepositoryItemRef"),
    "ExtrinsicObjectType": ("oots_lib.models.ResponseEvidences", "ExtrinsicObjectType"),
    "RegistryPackageType": ("oots_lib.models.ResponseEvidences", "RegistryPackageType"),
    "save_edm_request_to_redis": ("oots_lib.models.RequestEDM", "save_edm_request_to_redis"),
    "get_edm_request_from_redis": ("oots_lib.models.RequestEDM", "get_edm_request_from_redis"),
    "save_evidences_to_redis": ("oots_lib.models.ResponseEvidences", "save_evidences_to_redis"),
    "get_evidences_from_redis": ("oots_lib.models.ResponseEvidences", "get_evidences_from_redis"),
    "to_legacy_evidences_dict": ("oots_lib.models.ResponseEvidences", "to_legacy_evidences_dict"),
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
