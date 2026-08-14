import importlib

import pytest

import oots_lib
import oots_lib.models as models_package


@pytest.mark.parametrize("name", sorted(oots_lib._LAZY_IMPORTS))
def test_top_level_lazy_attributes_resolve(name):
    value = getattr(oots_lib, name)

    module_name, attr_name = oots_lib._LAZY_IMPORTS[name]
    assert value is getattr(importlib.import_module(module_name), attr_name)


# `oots_lib.models.Base` та `oots_lib.models.Person` — це ще й імена підмодулів,
# тому після їх імпорту атрибут пакета вказує на модуль, а не на клас.
SHADOWED_BY_SUBMODULE = {"Base", "Person"}


@pytest.mark.parametrize(
    "name", sorted(set(models_package._LAZY_IMPORTS) - SHADOWED_BY_SUBMODULE)
)
def test_models_lazy_attributes_resolve(name):
    value = getattr(models_package, name)

    module_name, attr_name = models_package._LAZY_IMPORTS[name]
    assert value is getattr(importlib.import_module(module_name), attr_name)


@pytest.mark.parametrize("name", sorted(SHADOWED_BY_SUBMODULE))
def test_models_names_shadowed_by_submodules(name):
    module_name, attr_name = models_package._LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)

    assert getattr(models_package, name) is module
    assert isinstance(getattr(module, attr_name), type)


def test_all_names_are_importable():
    assert set(oots_lib.__all__) <= set(oots_lib._LAZY_IMPORTS)
    assert set(models_package.__all__) <= set(models_package._LAZY_IMPORTS)


def test_lazy_attribute_is_cached_in_globals():
    getattr(oots_lib, "Person")
    assert "Person" in vars(oots_lib)


@pytest.mark.parametrize("package", [oots_lib, models_package])
def test_unknown_attribute_raises_attribute_error(package):
    with pytest.raises(AttributeError, match="no attribute 'Missing'"):
        getattr(package, "Missing")
