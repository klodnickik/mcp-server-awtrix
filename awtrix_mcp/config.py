"""Environment-driven settings for the AWTRIX MCP server, and the declarative
manifest schema (`apps/*.yaml`) consumed by the metric daemon."""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AwtrixSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AWTRIX_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    base_url: str = "http://awtrix3.local"


class ManifestError(Exception):
    """Base exception for manifest loading/validation failures."""


class SecretResolutionError(ManifestError):
    """Raised when a manifest references a `${VAR}` secret with no matching env var."""


_SECRET_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_secrets(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, str):

        def _substitute(match: re.Match) -> str:
            name = match.group(1)
            try:
                return env[name]
            except KeyError as exc:
                raise SecretResolutionError(f"undefined secret: {name}") from exc

        return _SECRET_PATTERN.sub(_substitute, value)
    if isinstance(value, dict):
        return {key: resolve_secrets(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_secrets(item, env) for item in value]
    return value


class BasicAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["http"] = "http"
    method: Literal["GET", "POST"] = "GET"
    url: str
    headers: dict[str, str] = {}
    body: dict[str, Any] | None = None
    auth: BasicAuthConfig | None = None


class TemplateTextSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    color: str | None = None


class DisplayRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: str
    icon: str | None = None
    notify: bool = False
    text: list[TemplateTextSegment]


class SubAppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    icon: str | None = None
    show_if: str | None = None
    text: list[TemplateTextSegment]


class ManifestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    name: str | None = None
    enabled: bool = True
    interval_seconds: int = Field(gt=0)
    source: SourceConfig
    transform: dict[str, str] = {}
    display: list[DisplayRule] = []
    sub_apps: list[SubAppConfig] = []

    @model_validator(mode="after")
    def _default_name(self) -> "ManifestConfig":
        self.name = self.name or self.app_id
        return self

    @model_validator(mode="after")
    def _require_display_or_sub_apps(self) -> "ManifestConfig":
        if not self.display and not self.sub_apps:
            raise ValueError("manifest must define at least one of 'display' or 'sub_apps'")
        return self


def load_manifest(path: Path, env: Mapping[str, str] | None = None) -> ManifestConfig:
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise ManifestError(f"{path}: unreadable: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path}: invalid YAML: {exc}") from exc
    try:
        resolved = resolve_secrets(raw, env or os.environ)
    except SecretResolutionError as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    try:
        return ManifestConfig.model_validate(resolved)
    except ValidationError as exc:
        # Deliberately omit the validation error's own message: it may embed
        # the post-substitution value of a field a `${SECRET}` was resolved
        # into, and this gets logged verbatim by the daemon's hot-reload path.
        raise ManifestError(f"{path}: manifest validation failed (see raw manifest for details)") from exc
