import pytest
import json
import os
from matika.database import Role, init_db
from matika.core.utils import load_metadata

def test_fallback_metadata(db):
    # Test fallback if no file exists
    metadata = load_metadata("nonexistent", model_class=Role)
    assert metadata is not None
    assert "browse_panel" in metadata
    assert "maintenance_panel" in metadata
    assert len(metadata["browse_panel"]["columns"]) > 0

def test_dev_version(client, db):
    from matika.core.paths import BASE_DIR
    version_file = os.path.join(BASE_DIR, "VERSION")
    with open(version_file) as f:
        expected_version = f.read().strip()

    init_db(db)
    resp = client.get("/about")
    assert resp.status_code == 200
    assert expected_version in resp.text
