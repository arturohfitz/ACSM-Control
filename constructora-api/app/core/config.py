from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ACSM Control"
    company_name: str = "ACSM S.A de C.V."
    owner_company_name: str = "ACSM S.A de C.V."
    environment: Literal["local", "development", "staging", "production"] = "local"
    database_url: str = Field(
        default="postgresql+psycopg://constructora:constructora@localhost:5432/constructora_db"
    )
    secret_key: str = "change-this-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    default_profit_percent: float = 0.15

    admin_full_name: str = "Administrador Maestro"
    admin_email: str = "admin@acsm-control.local"
    admin_password: str = "Admin12345!"
    auto_seed_admin: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
