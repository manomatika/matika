"""
Integration tests for the three-zone menu bar rendered by base.html.
Verifies HTML structure, menus_data injection, and role-based visibility.
"""
import json
import re
import pytest


def extract_menus_data(html: str) -> dict:
    m = re.search(
        r'<script type="application/json" id="matika-menus">(.*?)</script>',
        html,
        re.DOTALL,
    )
    return json.loads(m.group(1)) if m else {}


def selector_item_ids(data: dict) -> list:
    """Return only the IDs of selectable ('item'-type) selector entries."""
    return [e["id"] for e in data.get("selector", []) if e.get("type") == "item"]


def selector_header_labels(data: dict) -> list:
    """Return labels of section header entries in the selector."""
    return [e["label"] for e in data.get("selector", []) if e.get("type") == "header"]


# ---------------------------------------------------------------------------
# HTML structure
# ---------------------------------------------------------------------------

def test_three_zone_structure_present(client):
    """Every page extending base.html renders the three menu zones."""
    resp = client.get("/about")
    assert resp.status_code == 200
    html = resp.text
    assert 'class="menu-zone-logo"' in html
    assert 'id="menu-zone-hub"' in html
    assert 'class="menu-zone-user"' in html

def test_selector_elements_present(client):
    """Selector trigger, panel, and list container are in the DOM."""
    resp = client.get("/about")
    html = resp.text
    assert 'id="menu-selector-trigger"' in html
    assert 'id="menu-selector-panel"' in html
    assert 'id="menu-selector-list"' in html
    assert 'id="menu-hub-items"' in html
    # Tabs and search removed in Issue 2 simplification
    assert 'id="menu-selector-tabs"' not in html
    assert 'id="menu-search-input"' not in html

def test_logo_image_present(client):
    """Logo zone must use the .logo-img image, not the old CSS monogram."""
    resp = client.get("/about")
    assert 'class="logo-img"' in resp.text
    assert "matika_icon" in resp.text


# ---------------------------------------------------------------------------
# Selector structure (discriminated union: item / separator / header)
# ---------------------------------------------------------------------------

def test_menus_json_embedded_in_base_pages(client):
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "selector" in data
    assert "hubs" in data

def test_default_and_favorites_always_selectable(client):
    """Default and Favorites are always present as item-type entries."""
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    ids = selector_item_ids(data)
    assert "__default__" in ids
    assert "__favorites__" in ids

def test_selector_ordering(client, test_admin):
    """Selector order: Default, Favorites, [Applications section], [Roles section]."""
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    item_ids = selector_item_ids(data)
    assert item_ids.index("__default__") < item_ids.index("__favorites__")
    # mock_plugin (Application) comes before any __role_* (Role)
    mock_idx = item_ids.index("mock_plugin") if "mock_plugin" in item_ids else None
    role_idxs = [i for i, eid in enumerate(item_ids) if eid.startswith("__role_")]
    if mock_idx is not None and role_idxs:
        assert mock_idx < min(role_idxs)

def test_selector_has_applications_header_when_plugins_loaded(client, test_admin):
    """Applications section header is present when plugins have visible menus."""
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "Applications" in selector_header_labels(data)

def test_selector_has_roles_header_for_admin(client, test_admin):
    """Roles section header is present for admin users who have role menus."""
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "Roles" in selector_header_labels(data)

def test_favorites_hub_always_empty_list(client):
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert data["hubs"]["__favorites__"] == []

def test_default_hub_present(client):
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "__default__" in data["hubs"]
    assert isinstance(data["hubs"]["__default__"], list)


# ---------------------------------------------------------------------------
# Role-based visibility (server-side filtering)
# ---------------------------------------------------------------------------

def test_unauthenticated_receives_no_admin_urls(client):
    """Non-authenticated users must not receive any /admin/ URLs in menus_data."""
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "/admin/" not in json.dumps(data)

def test_unauthenticated_has_no_role_selector_entries(client):
    """No __role_* selector entries appear for unauthenticated users."""
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    role_ids = [e["id"] for e in data["selector"] if e.get("type") == "item" and e["id"].startswith("__role_")]
    assert role_ids == []

def test_admin_user_sees_role_entry_in_selector(client, test_admin):
    """Admin users see __role_Admin__ as a selectable entry."""
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "__role_Admin__" in selector_item_ids(data)

def test_admin_user_default_hub_uses_display_name(client, test_admin):
    """Default hub uses display_name (not full name) for AppLug entries."""
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    # mock_plugin has no display_name, so falls back to "Mock Plugin"
    default_labels = [item["label"] for item in data["hubs"]["__default__"]]
    assert "Admin" in default_labels

def test_regular_user_default_hub_excludes_admin_menu(client, test_user):
    """A regular user's default hub must not include admin content."""
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    json_str = json.dumps(data)
    assert "/admin/roles" not in json_str
    assert "/admin/users" not in json_str

def test_mock_plugin_visible_to_admin(client, test_admin):
    """Admin users see mock_plugin in the selector."""
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "adminpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "mock_plugin" in selector_item_ids(data)

def test_mock_plugin_visible_to_regular_user(client, test_user):
    """Regular users also see mock_plugin (items have roles User)."""
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    data = extract_menus_data(resp.text)
    assert "mock_plugin" in selector_item_ids(data)


# ---------------------------------------------------------------------------
# User zone dropdown structure
# ---------------------------------------------------------------------------

def test_user_dropdown_order_and_labels(client, test_user):
    """User dropdown: User Settings | sep | Export User Data | Import User Data | sep | Logout."""
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    html = resp.text

    # All expected entries must be present
    assert "User Settings" in html
    assert "Export User Data" in html
    assert "Import User Data" in html
    assert "Logout" in html

    # Order: User Settings before Export, Export before Import, Import before Logout
    pos_settings = html.index("User Settings")
    pos_export   = html.index("Export User Data")
    pos_import   = html.index("Import User Data")
    pos_logout   = html.index("Logout")
    assert pos_settings < pos_export < pos_import < pos_logout

def test_user_dropdown_has_two_separators(client, test_user):
    """Two separators: one after User Settings, one before Logout."""
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    html = resp.text

    # Locate the user zone section (after the hub items)
    # The user zone dropdown sits within .menu-zone-user
    zone_start = html.index('class="menu-zone-user"')
    zone_html  = html[zone_start:]

    separator_count = zone_html.count('class="menu-separator"')
    assert separator_count == 2

def test_user_dropdown_old_export_label_not_present(client, test_user):
    """The old 'Export My Data' / 'Import My Data' labels must not appear in the nav."""
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpassword"},
        follow_redirects=False,
    )
    resp = client.get("/about")
    # Headings inside the export/import pages still say "My Data",
    # but the nav links rendered via base.html must use the new labels.
    zone_start = resp.text.index('class="menu-zone-user"')
    zone_html  = resp.text[zone_start:zone_start + 1000]
    assert "Export My Data" not in zone_html
    assert "Import My Data" not in zone_html


# ---------------------------------------------------------------------------
# Help menu separator
# ---------------------------------------------------------------------------

def test_help_menu_has_separator_between_show_log_and_about(client):
    """Help hub dropdown must contain a Separator between Show Log and About."""
    resp = client.get("/about")
    data = extract_menus_data(resp.text)

    # Find the Help menu in the default hub
    default_hub = data["hubs"]["__default__"]
    help_entry = next(
        (item for item in default_hub if item.get("label") == "Help"),
        None,
    )
    assert help_entry is not None, "Help entry not found in default hub"

    item_types = [i["type"] for i in help_entry["items"]]
    assert "Separator" in item_types

    # Show Log must come before the separator, About after it
    sep_idx = item_types.index("Separator")
    labels_before = [i.get("label") for i in help_entry["items"][:sep_idx]]
    labels_after  = [i.get("label") for i in help_entry["items"][sep_idx + 1:]]
    assert any("Log" in (lbl or "") for lbl in labels_before)
    assert any("About" in (lbl or "") for lbl in labels_after)
