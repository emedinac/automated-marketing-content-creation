from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment and local ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_cloud_project: str = Field(
        default="",
        validation_alias="GOOGLE_CLOUD_PROJECT",
    )
    google_cloud_location: str = Field(
        default="global",
        validation_alias="GOOGLE_CLOUD_LOCATION",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias="GEMINI_MODEL",
    )
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    prompt_version: str = Field(default="v1", validation_alias="PROMPT_VERSION")
