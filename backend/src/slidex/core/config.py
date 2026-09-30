"""Application settings, read from backend/.env and SLIDEX_* environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]

Effort = Literal["none", "low", "medium", "high", "xhigh"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="SLIDEX_",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "SLIDEX_OPENAI_API_KEY")
    )
    fake_llm: bool = False

    model_strong: str = "gpt-5.4-nano"
    model_vision: str = "gpt-5.4-nano"
    model_bulk: str = "gpt-5.4-nano"
    model_search: str = "gpt-5.4-nano"
    model_embed: str = "text-embedding-3-small"
    effort_strong: Effort = "medium"
    effort_vision: Effort = "low"
    effort_bulk: Effort = "none"
    effort_search: Effort = "low"

    data_dir: Path = Path("../data")
    soffice: Path = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    concurrency: int = Field(default=6, ge=1, le=32)
    max_topics: int = Field(default=15, ge=1, le=50)
    searches_per_topic: int = Field(default=2, ge=1, le=5)
    pages_per_topic: int = Field(default=8, ge=1, le=20)
    web_search_fee_usd: float = Field(default=0.01, ge=0)

    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def data_path(self) -> Path:
        path = self.data_dir if self.data_dir.is_absolute() else BACKEND_DIR / self.data_dir
        return path.resolve()

    @property
    def db_path(self) -> Path:
        return self.data_path / "slidex.db"

    @property
    def files_path(self) -> Path:
        return self.data_path / "files"

    @property
    def api_key_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value().strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
