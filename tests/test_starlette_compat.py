"""Regression test: starlette.testclient must not emit StarletteDeprecationWarning.

This test catches any reversion to httpx (vs httpx2) as the starlette TestClient
backend. starlette 1.2.0+ emits StarletteDeprecationWarning (UserWarning subclass,
always-visible) when httpx is installed but httpx2 is absent. The fix: declare
httpx2 as the direct dep instead of httpx.

Without the fix, this test fails with a caught StarletteDeprecationWarning.
With the fix (httpx2 installed), no warning fires.
"""
import sys
import warnings


def test_no_starlette_deprecation_on_testclient_import():
    # Remove cached testclient modules so the module-level import check fires.
    to_remove = [k for k in sys.modules if "starlette.testclient" in k or "fastapi.testclient" in k]
    for key in to_remove:
        del sys.modules[key]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import starlette.testclient  # noqa: F401

    httpx_warnings = [
        w for w in caught
        if issubclass(w.category, UserWarning) and "httpx" in str(w.message).lower()
    ]
    assert not httpx_warnings, (
        f"StarletteDeprecationWarning fired on TestClient import — "
        f"httpx2 may not be installed. Caught: {httpx_warnings}"
    )
