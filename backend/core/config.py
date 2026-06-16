"""
Core configuration - reads from environment variables.
Never hardcode secrets here.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Saundarya Beauty Care"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_USE_STRONG_RANDOM_KEY_32CHARS+")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Oracle DB
    ORACLE_USER: str = os.getenv("ORACLE_USER", "SAUNDARYA")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "Test123")
    ORACLE_DSN: str = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")
    ORACLE_WALLET_DIR: str = os.getenv("ORACLE_WALLET_DIR", "")
    ORACLE_WALLET_PASSWORD: str = os.getenv("ORACLE_WALLET_PASSWORD", "")
    ORACLE_MIN_POOL: int = 2
    ORACLE_MAX_POOL: int = 10
    ORACLE_INCREMENT: int = 1

    # WhatsApp (UltraMsg / CallMeBot / Official API)
    WA_API_URL: str = os.getenv("WA_API_URL", "")
    WA_INSTANCE_ID: str = os.getenv("WA_INSTANCE_ID", "")
    WA_TOKEN: str = os.getenv("WA_TOKEN", "")
    # Provider: 'ultramsg' | 'callmebot' | 'meta'
    WA_PROVIDER: str = os.getenv("WA_PROVIDER", "ultramsg")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN: int = 10

    # PDF generation
    PDF_DIR: str = "/tmp/saundarya_pdfs"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
