"""Applug functional-test contract — Layer 3 canonical constants.

The per-component declarative convention for functional tests:
  - Discovery: applug places <applug>_functional_tests.json alongside its
    *_screens.json. The gate discovers all *_functional_tests.json files from
    the source clone generically (no applug names in gate code).
  - Declaration: JSON manifest with schema_version = FUNCTIONAL_TEST_SCHEMA,
    listing test_id/description/module/function/tags for each test.
  - Implementation: companion <applug>_functional_tests.py with functions of
    signature def test_xxx(base_url: str, session) -> None; raises AssertionError
    on failure.
  - Invocation: gate imports the named module from the source clone and calls
    each declared function with base_url=product_url, session=auth_session.
  - No test code ships in the product runtime (source-tree-only files).

ahimsa mirrors FUNCTIONAL_TEST_SCHEMA and FUNCTIONAL_TESTS_SUFFIX in
scripts/screen_manifest.py. Cross-repo parity against these canonical values is
asserted in ahimsa's gate (tests/test_screen_schema_parity.py) — the layer that
checks out both repos — per manomatika/matika#105; it is no longer a matika unit
test (that made matika CI red without the ahimsa sibling).
"""

FUNCTIONAL_TEST_SCHEMA = "1.0"
FUNCTIONAL_TESTS_SUFFIX = "_functional_tests.json"
