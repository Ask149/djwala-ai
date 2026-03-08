"""Configuration module using pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit: str = "5/minute"
    database_path: str = "djwala_cache.db"
    youtube_api_key: str | None = None  # Optional: YouTube API v3 fallback (only needed if yt-dlp is blocked)

    # OAuth (optional — app works without login)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    session_secret: str | None = None

    @property
    def oauth_enabled(self) -> bool:
        """True if at least one OAuth provider is configured."""
        return bool(
            (self.google_client_id and self.google_client_secret)
            or (self.spotify_client_id and self.spotify_client_secret)
        )

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def spotify_enabled(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)
    
    model_config = SettingsConfigDict(
        env_prefix="DJWALA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
