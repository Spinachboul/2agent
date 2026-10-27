
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BRD Copilot"
    app_env: str = "development"
    storage_root: Path = Path("./storage")
    max_upload_mb: int = Field(default=50, gt=0)

    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str

    azure_input_price_per_1m: float = Field(default=0, ge=0)
    azure_output_price_per_1m: float = Field(default=0, ge=0)

    checkpoint_db: Path = Path("./storage/checkpoints.sqlite")


@lru_cache
def get_settings() -> Settings:
    settings = Settings() # type: ignore[call-arg]
    settings.storage_root.mkdir(parents=True, exist_ok=True)

    for name in (
        "documents",
        "generated_json",
        "workflows",
        "sessions",
        "token_usage",
        "audit_logs",
    ):
        (settings.storage_root / name).mkdir(
            parents=True, exist_ok=True
        )

    return settings
