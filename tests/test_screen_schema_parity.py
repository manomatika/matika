"""M4: cross-repo schema-constant parity between matika and ahimsa.

Reads the ahimsa sibling at ../../ahimsa/scripts/screen_manifest.py relative
to this test file's location and extracts its SUPPORTED_SCHEMA and ALLOWED_VERBS
constants using ast. Any drift from matika's canonical values fails CI.

Layer-3 contract constants (FUNCTIONAL_TEST_SCHEMA, FUNCTIONAL_TESTS_SUFFIX)
will be added here once manomatika/ahimsa#101 lands and mirrors those values.
"""
import ast
from pathlib import Path

import pytest

from matika.core.screen_loader import ALLOWED_VERBS, SUPPORTED_SCHEMA


# Resolve ahimsa sibling path from the matika repo root.
_MATIKA_ROOT = Path(__file__).parent.parent
_AHIMSA_MANIFEST = _MATIKA_ROOT / ".." / "ahimsa" / "scripts" / "screen_manifest.py"


def _extract_constants(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    constants = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                val = node.value
                # Try literal first.
                try:
                    constants[target.id] = ast.literal_eval(val)
                    continue
                except (ValueError, TypeError):
                    pass
                # Handle frozenset({...}) or set({...}) calls.
                if (
                    isinstance(val, ast.Call)
                    and isinstance(val.func, ast.Name)
                    and val.func.id in ("frozenset", "set")
                    and len(val.args) == 1
                ):
                    try:
                        inner = ast.literal_eval(val.args[0])
                        constants[target.id] = frozenset(inner) if val.func.id == "frozenset" else set(inner)
                    except (ValueError, TypeError):
                        pass
    return constants


@pytest.fixture(scope="module")
def ahimsa_constants():
    if not _AHIMSA_MANIFEST.exists():
        pytest.fail(
            f"ahimsa sibling not found at {_AHIMSA_MANIFEST}. "
            f"Expected sibling repo at ~/dev/projects/ahimsa/."
        )
    return _extract_constants(_AHIMSA_MANIFEST)


class TestSchemaConstantParity:
    def test_supported_schema_matches(self, ahimsa_constants):
        ahimsa_val = ahimsa_constants.get("SUPPORTED_SCHEMA")
        assert ahimsa_val is not None, (
            "SUPPORTED_SCHEMA not found in ahimsa scripts/screen_manifest.py"
        )
        assert ahimsa_val == SUPPORTED_SCHEMA, (
            f"SUPPORTED_SCHEMA drift: matika={SUPPORTED_SCHEMA!r}, "
            f"ahimsa={ahimsa_val!r}"
        )

    def test_allowed_verbs_matches(self, ahimsa_constants):
        ahimsa_val = ahimsa_constants.get("ALLOWED_VERBS")
        assert ahimsa_val is not None, (
            "ALLOWED_VERBS not found in ahimsa scripts/screen_manifest.py"
        )
        # ast.literal_eval of a frozenset call returns a frozenset
        if isinstance(ahimsa_val, (set, frozenset)):
            ahimsa_set = frozenset(ahimsa_val)
        else:
            pytest.fail(
                f"ALLOWED_VERBS in ahimsa has unexpected type: {type(ahimsa_val)}"
            )
        assert ahimsa_set == ALLOWED_VERBS, (
            f"ALLOWED_VERBS drift:\n"
            f"  matika:  {sorted(ALLOWED_VERBS)}\n"
            f"  ahimsa:  {sorted(ahimsa_set)}"
        )

    def test_functional_test_schema_parity_if_present(self, ahimsa_constants):
        """Once manomatika/ahimsa#101 lands, FUNCTIONAL_TEST_SCHEMA must match matika canon."""
        from matika.core.functional_test_contract import FUNCTIONAL_TEST_SCHEMA
        ahimsa_val = ahimsa_constants.get("FUNCTIONAL_TEST_SCHEMA")
        if ahimsa_val is None:
            return  # not yet mirrored; parity enforced after ahimsa#101 merges
        assert ahimsa_val == FUNCTIONAL_TEST_SCHEMA, (
            f"FUNCTIONAL_TEST_SCHEMA drift: matika={FUNCTIONAL_TEST_SCHEMA!r}, "
            f"ahimsa={ahimsa_val!r}"
        )

    def test_functional_tests_suffix_parity_if_present(self, ahimsa_constants):
        """Once manomatika/ahimsa#101 lands, FUNCTIONAL_TESTS_SUFFIX must match matika canon."""
        from matika.core.functional_test_contract import FUNCTIONAL_TESTS_SUFFIX
        ahimsa_val = ahimsa_constants.get("FUNCTIONAL_TESTS_SUFFIX")
        if ahimsa_val is None:
            return  # not yet mirrored; parity enforced after ahimsa#101 merges
        assert ahimsa_val == FUNCTIONAL_TESTS_SUFFIX, (
            f"FUNCTIONAL_TESTS_SUFFIX drift: matika={FUNCTIONAL_TESTS_SUFFIX!r}, "
            f"ahimsa={ahimsa_val!r}"
        )
