"""Configuration for the Content Judge agent."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    gemini_api_key: str
    access_key_id: str | None = None
    secret_key: str | None = None
    default_model: str = "gemini-3.1-pro-preview"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def hive_api_token(self) -> str | None:
        """The Hive API auth token (Secret Key)."""
        return self.secret_key


def get_settings() -> Settings:
    """Load and return application settings."""
    return Settings()
