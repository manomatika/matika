"""
Framework contract: maintenance_activity_base.html renders <select> options
generically from a route-supplied `option_sources` dict, keyed by each select
field's `options_source` value. The framework template must NOT know any
applug domain vocabulary (e.g. "security_types", "asset_classes").

These tests would have caught the field-name drift between eyerate's metadata
and matika's template branches that left the financial_security_type dropdown
empty in production (see manomatika/eyerate#21).
"""
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "matika", "templates")
)


def _render(metadata, *, option_sources=None):
    """Render maintenance_activity_base.html with a minimal stubbed context.

    The base template (base.html) has many context dependencies; we stub the
    minimum needed so the render completes and we can inspect the rendered
    <select>s. We are testing the framework contract, not the surrounding chrome.
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["getattr"] = getattr
    env.globals["hasattr"] = hasattr
    env.globals["isinstance"] = isinstance
    env.globals["str"] = str

    template = env.get_template("maintenance_activity_base.html")
    return template.render(
        title="Test",
        metadata=metadata,
        option_sources=option_sources or {},
        # Stub everything base.html consumes:
        t={},
        user=None,
        csrf_token="",
        user_id="",
        user_default_menu="",
        fresh_login=False,
        menus_data={"selector": [], "hubs": {}},
        securities=[],
    )


def _extract_select_body(html, field_name):
    """Return the inner HTML of <select id="field-{field_name}">…</select>."""
    pattern = re.compile(
        rf'<select id="field-{re.escape(field_name)}"[^>]*>(.*?)</select>',
        re.DOTALL,
    )
    m = pattern.search(html)
    assert m, f"<select id='field-{field_name}'> not found in rendered HTML"
    return m.group(1)


def _metadata_with_select(name, *, options_source, required=False):
    return {
        "browse_panel": {"columns": [], "search_fields": []},
        "maintenance_panel": {
            "buttons": ["new"],
            "fields": [
                {
                    "name": name,
                    "label_key": f"label_{name}",
                    "type": "select",
                    "options_source": options_source,
                    "required": required,
                    "read_only": False,
                }
            ],
        },
    }


def test_select_renders_options_from_option_sources():
    """Given option_sources[X] = [...], the select for a field with
    options_source=X emits exactly those options."""
    metadata = _metadata_with_select("color", options_source="palette", required=True)
    html = _render(metadata, option_sources={"palette": ["red", "green", "blue"]})

    body = _extract_select_body(html, "color")
    assert '<option value="red">red</option>' in body
    assert '<option value="green">green</option>' in body
    assert '<option value="blue">blue</option>' in body
    # Required → no leading blank option:
    assert '<option value=""></option>' not in body
    assert body.count("<option") == 3


def test_template_has_no_applug_domain_terms():
    """The framework template must not know any applug vocabulary. If a future
    refactor reintroduces a hardcoded branch this test fails immediately."""
    with open(os.path.join(TEMPLATE_DIR, "maintenance_activity_base.html")) as f:
        src = f.read()
    for forbidden in (
        "security_types",
        "financial_security_types",
        "asset_classes",
        "FinancialSecurity",
    ):
        assert forbidden not in src, (
            f"Domain term {forbidden!r} leaked into matika framework template "
            f"maintenance_activity_base.html — the template must remain "
            f"applug-agnostic."
        )


def test_unknown_options_source_degrades_safely():
    """If a field declares an options_source that's not present in
    option_sources, render an empty select — never crash."""
    metadata = _metadata_with_select("x", options_source="nope", required=True)
    html = _render(metadata, option_sources={"other": ["a", "b"]})

    body = _extract_select_body(html, "x")
    assert "<option" not in body


def test_missing_options_source_attribute_degrades_safely():
    """If a select field omits options_source entirely, render an empty
    select — never crash, never iterate None."""
    metadata = {
        "browse_panel": {"columns": [], "search_fields": []},
        "maintenance_panel": {
            "buttons": ["new"],
            "fields": [
                {
                    "name": "y",
                    "label_key": "label_y",
                    "type": "select",
                    "required": True,
                    "read_only": False,
                }
            ],
        },
    }
    html = _render(metadata, option_sources={"anything": ["a"]})

    body = _extract_select_body(html, "y")
    assert "<option" not in body


def test_optional_select_gets_leading_blank_option():
    """Non-required selects receive a leading <option value=""> so the user
    can clear their choice — preserving the pre-refactor UX for nullable
    columns (e.g. asset_class)."""
    metadata = _metadata_with_select("opt", options_source="kinds", required=False)
    html = _render(metadata, option_sources={"kinds": ["one", "two"]})

    body = _extract_select_body(html, "opt")
    assert '<option value=""></option>' in body
    assert '<option value="one">one</option>' in body
    assert '<option value="two">two</option>' in body


def test_multiple_fields_dispatch_independently():
    """Two select fields with different options_source values draw from
    different lists — confirms the generic dispatch isn't accidentally
    keyed on something other than each field's own options_source."""
    metadata = {
        "browse_panel": {"columns": [], "search_fields": []},
        "maintenance_panel": {
            "buttons": ["new"],
            "fields": [
                {"name": "a", "label_key": "k", "type": "select",
                 "options_source": "first", "required": True, "read_only": False},
                {"name": "b", "label_key": "k", "type": "select",
                 "options_source": "second", "required": True, "read_only": False},
            ],
        },
    }
    html = _render(
        metadata,
        option_sources={"first": ["X", "Y"], "second": ["P", "Q", "R"]},
    )
    a_body = _extract_select_body(html, "a")
    b_body = _extract_select_body(html, "b")
    assert '<option value="X">X</option>' in a_body
    assert '<option value="P">P</option>' in b_body
    assert "P" not in a_body
    assert "X" not in b_body
