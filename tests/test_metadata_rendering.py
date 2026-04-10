import pytest
import json
import os
from matika.database import Security, SecurityType, AssetClass, init_db
from matika.core.utils import load_metadata

def test_load_metadata_pattern(db):
    # Test that it finds the new pattern
    metadata = load_metadata("securities", model_class=Security)
    assert metadata is not None
    assert "browse_panel" in metadata
    assert "search_fields" in metadata["browse_panel"]

def test_fallback_metadata(db):
    # Test fallback if no file exists
    metadata = load_metadata("nonexistent", model_class=Security)
    assert metadata is not None
    assert "browse_panel" in metadata
    assert "maintenance_panel" in metadata
    assert len(metadata["browse_panel"]["columns"]) > 0

def test_search_fields_rendered(client, test_admin, db):
    init_db(db)
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    resp = client.get("/admin/securities")
    assert resp.status_code == 200
    
    # Check if search fields from metadata are in the dropdown
    # According to securities_maint_activity_metadata.json: symbol, name
    assert '<option value="symbol">' in resp.text
    assert '<option value="name">' in resp.text
    # current_price should NOT be in search_fields dropdown based on our metadata
    # but it IS in the columns. Let's verify it's NOT in the select options for search-field
    
    import re
    search_field_select = re.search(r'<select id="search-field".*?>(.*?)</select>', resp.text, re.DOTALL)
    assert search_field_select is not None
    options = search_field_select.group(1)
    assert 'value="symbol"' in options
    assert 'value="name"' in options
    assert 'value="current_price"' not in options

def test_dev_version(client, db):
    # Sync version to DB
    init_db(db)
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "0.0.1" in resp.text

def test_layout_panels_presence(client, test_admin, db):
    init_db(db)
    client.post("/login", data={"email": test_admin.email, "password": "adminpassword"}, follow_redirects=False)
    
    resp = client.get("/admin/securities")
    assert resp.status_code == 200
    assert 'class="title-panel"' in resp.text
    assert 'class="activities-main-panel"' in resp.text
    assert 'class="status-error-panel"' in resp.text
    assert 'id="btn-search"' in resp.text
    assert 'Securities' in resp.text # Title Panel content

