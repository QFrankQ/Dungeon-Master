"""
Application settings using Pydantic Settings.

Loads configuration from environment variables with validation.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Discord Configuration
    discord_bot_token: Optional[str] = None
    discord_application_id: Optional[str] = None

    # Gemini AI Configuration (accepts both GEMINI_API_KEY and GOOGLE_API_KEY)
    gemini_api_key: Optional[str] = Field(
        default=None,
        validation_alias="google_api_key"
    )
    gemini_api_key_paid_tier: Optional[str] = Field(
        default=None,
        validation_alias="google_api_key_paid_tier"
    )

    # Database Configuration
    database_url: str = "postgresql+asyncpg://dnd:dev_password@localhost:5432/dnd_bot"

    # BYOK Encryption (for Phase 3)
    encryption_key: Optional[str] = None

    # Memory Configuration (optional overrides)
    dm_max_tokens: int = 10000
    dm_min_tokens: int = 5000
    dm_enable_memory: bool = True
    dm_enable_summarization: bool = True

    def get_encryption_key(self) -> Optional[bytes]:
        """Get encryption key as bytes, or None if not configured."""
        if not self.encryption_key:
            return None
        return self.encryption_key.encode()

    @classmethod
    def generate_encryption_key(cls) -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore
    return _settings
