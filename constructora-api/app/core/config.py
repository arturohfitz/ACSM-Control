from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://constructora:constructora@localhost:5432/constructora_db"
DEFAULT_SECRET_KEY = "change-this-secret-key"
DEFAULT_ADMIN_PASSWORD = "Admin12345!"


class Settings(BaseSettings):
    app_name: str = "ACSM Control"
    company_name: str = "ACSM S.A de C.V."
    owner_company_name: str = "ACSM S.A de C.V."
    environment: Literal["local", "development", "staging", "production"] = "local"
    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    secret_key: str = DEFAULT_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    default_profit_percent: float = 0.15
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )
    login_max_attempts: int = 5
    login_window_seconds: int = 15 * 60
    login_lock_seconds: int = 15 * 60
    email_encryption_key: str | None = None

    admin_full_name: str = "Administrador Maestro"
    admin_email: str = "admin@acsm-control.local"
    admin_password: str = DEFAULT_ADMIN_PASSWORD
    auto_seed_admin: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment != "production":
            return self
        unsafe: list[str] = []
        if self.database_url == DEFAULT_DATABASE_URL:
            unsafe.append("DATABASE_URL")
        if self.secret_key == DEFAULT_SECRET_KEY or len(self.secret_key) < 32:
            unsafe.append("SECRET_KEY")
        if self.admin_password == DEFAULT_ADMIN_PASSWORD:
            unsafe.append("ADMIN_PASSWORD")
        if not self.cors_origins or "*" in self.cors_origins:
            unsafe.append("CORS_ORIGINS")
        if not self.email_encryption_key:
            unsafe.append("EMAIL_ENCRYPTION_KEY")
        if unsafe:
            joined = ", ".join(unsafe)
            raise ValueError(f"Configuracion insegura para produccion: {joined}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
