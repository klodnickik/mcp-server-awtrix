"""Environment-driven settings for the AWTRIX MCP server."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AwtrixSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AWTRIX_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    base_url: str = "http://awtrix3.local"
