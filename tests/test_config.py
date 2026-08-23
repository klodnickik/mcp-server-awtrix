"""Tests for environment-driven settings loading and manifest schema/loading."""

import textwrap

import pytest
from pydantic import ValidationError

from awtrix_mcp.config import (
    AwtrixSettings,
    ManifestConfig,
    ManifestError,
    SecretResolutionError,
    load_manifest,
    resolve_secrets,
)


def test_awtrix_settings_reads_base_url_from_env(monkeypatch):
    monkeypatch.setenv("AWTRIX_BASE_URL", "http://192.168.1.50")
    settings = AwtrixSettings(_env_file=None)
    assert settings.base_url == "http://192.168.1.50"


def test_awtrix_settings_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("AWTRIX_BASE_URL", raising=False)
    settings = AwtrixSettings(_env_file=None)
    assert settings.base_url == "http://awtrix3.local"


def test_resolve_secrets_substitutes_env_var():
    assert resolve_secrets("Bearer ${TOKEN}", {"TOKEN": "abc123"}) == "Bearer abc123"


def test_resolve_secrets_raises_for_undefined_var():
    with pytest.raises(SecretResolutionError):
        resolve_secrets("${MISSING_VAR}", {})


def test_resolve_secrets_recurses_into_dicts_and_lists():
    value = {"a": "${X}", "b": ["${Y}", 1, None]}
    resolved = resolve_secrets(value, {"X": "x", "Y": "y"})
    assert resolved == {"a": "x", "b": ["y", 1, None]}


def test_load_manifest_matches_checkly_shape(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    manifest_path.write_text(
        textwrap.dedent(
            """
            app_id: "checkly"
            name: "checkly_status"
            interval_seconds: 60
            source:
              type: "http"
              url: "https://api.checklyhq.com/v1/checks"
              headers:
                Authorization: "Bearer ${CHECKLY_API_KEY}"
            transform:
              total: "len(data)"
              failures: "sum(1 for c in data if c.get('hasFailures'))"
            display:
              - condition: "failures > 0"
                notify: true
                text:
                  - { text: "FAIL ", color: "FF0000" }
              - condition: "default"
                text:
                  - { text: "UP ", color: "00FF00" }
            """
        )
    )
    manifest = load_manifest(manifest_path, env={"CHECKLY_API_KEY": "secret"})
    assert manifest.app_id == "checkly"
    assert manifest.name == "checkly_status"
    assert manifest.source.headers["Authorization"] == "Bearer secret"
    assert len(manifest.display) == 2
    assert manifest.display[0].notify is True


def test_load_manifest_rejects_unknown_top_level_key(tmp_path):
    manifest_path = tmp_path / "bad.yaml"
    manifest_path.write_text(
        textwrap.dedent(
            """
            app_id: "t"
            interval_seconds: 1
            unexpected_key: true
            source: { type: "http", url: "http://x" }
            display: [{ condition: "default", text: [{ text: "hi" }] }]
            """
        )
    )
    with pytest.raises(ManifestError):
        load_manifest(manifest_path, env={})


def test_load_manifest_rejects_missing_display_and_sub_apps(tmp_path):
    manifest_path = tmp_path / "bad.yaml"
    manifest_path.write_text(
        textwrap.dedent(
            """
            app_id: "t"
            interval_seconds: 1
            source: { type: "http", url: "http://x" }
            """
        )
    )
    with pytest.raises(ManifestError):
        load_manifest(manifest_path, env={})


def test_manifest_config_missing_display_and_sub_apps_raises_validation_error():
    with pytest.raises(ValidationError):
        ManifestConfig.model_validate(
            {
                "app_id": "t",
                "interval_seconds": 1,
                "source": {"type": "http", "url": "http://x"},
            }
        )
