from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sentinel Atlas Backend"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"
    database_url: str = Field(
        default="sqlite:///./sentinel_atlas_dev.db",
        description="Use postgresql+psycopg://... for Postgres/PostGIS deployments.",
    )
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    create_db_on_startup: bool = True
    enable_experimental_tabpfn: bool = Field(
        default=False,
        description="Enable the disabled-by-default experimental TabPFN-Time-Series benchmark model.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENTINEL_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
