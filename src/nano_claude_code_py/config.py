from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    model: str = "claude-sonnet-4-0"
    permission_mode: str = "ask"
    session_dir: Path = Path.home() / ".nano-claude" / "sessions"
    cwd: Path = Path.cwd()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )
