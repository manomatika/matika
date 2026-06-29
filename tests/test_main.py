"""Tests for src/matika/main.py routes including /healthz."""
import pytest


class TestHealthzEndpoint:
    def test_healthz_returns_200_without_auth(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_healthz_returns_product_version_status(self, client):
        resp = client.get("/healthz")
        data = resp.json()
        assert data["product"] == "ManoMatika"
        assert isinstance(data["version"], str)
        assert data["status"] == "ok"
        assert "pid" not in data

    def test_healthz_excludes_secrets(self, client):
        resp = client.get("/healthz")
        data = resp.json()
        allowed = {"product", "version", "status"}
        assert set(data.keys()) <= allowed, f"unexpected keys: {set(data.keys()) - allowed}"

    def test_healthz_makes_no_db_calls(self, client, monkeypatch):
        from matika import database
        original = database.SessionLocal
        calls = []

        def patched_session():
            calls.append(1)
            return original()

        monkeypatch.setattr(database, "SessionLocal", patched_session)
        client.get("/healthz")
        assert not calls, "/healthz must not open a database session"
