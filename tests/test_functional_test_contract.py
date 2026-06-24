"""Tests for src/matika/core/functional_test_contract.py — Layer-3 contract constants."""
from matika.core.functional_test_contract import (
    FUNCTIONAL_TEST_SCHEMA,
    FUNCTIONAL_TESTS_SUFFIX,
)


def test_functional_test_schema_value():
    assert FUNCTIONAL_TEST_SCHEMA == "1.0"


def test_functional_test_schema_is_string():
    assert isinstance(FUNCTIONAL_TEST_SCHEMA, str)


def test_functional_tests_suffix_value():
    assert FUNCTIONAL_TESTS_SUFFIX == "_functional_tests.json"


def test_functional_tests_suffix_is_string():
    assert isinstance(FUNCTIONAL_TESTS_SUFFIX, str)


def test_functional_tests_suffix_starts_with_underscore():
    """Suffix follows the same leading-underscore convention as _screens.json."""
    assert FUNCTIONAL_TESTS_SUFFIX.startswith("_")


def test_functional_tests_suffix_ends_with_json():
    assert FUNCTIONAL_TESTS_SUFFIX.endswith(".json")
