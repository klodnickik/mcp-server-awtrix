"""Tests for environment-driven settings loading."""

from awtrix_mcp.config import AwtrixSettings


def test_awtrix_settings_reads_base_url_from_env(monkeypatch):
    monkeypatch.setenv("AWTRIX_BASE_URL", "http://192.168.1.50")
    settings = AwtrixSettings(_env_file=None)
    assert settings.base_url == "http://192.168.1.50"


def test_awtrix_settings_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("AWTRIX_BASE_URL", raising=False)
    settings = AwtrixSettings(_env_file=None)
    assert settings.base_url == "http://awtrix3.local"
