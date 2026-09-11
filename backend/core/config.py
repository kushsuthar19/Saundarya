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

    # WhatsApp (UltraMsg / CallMeBot / Meta Cloud API / AiSensy)
    WA_API_URL: str = os.getenv("WA_API_URL", "")
    WA_INSTANCE_ID: str = os.getenv("WA_INSTANCE_ID", "")
    WA_TOKEN: str = os.getenv("WA_TOKEN", "")
    # AiSensy sends via a pre-approved WhatsApp template ("campaign"), not
    # free-form text — this is the exact campaign name from the AiSensy
    # dashboard. Only used when WA_PROVIDER=aisensy.
    WA_CAMPAIGN_NAME: str = os.getenv("WA_CAMPAIGN_NAME", "")
    # Provider: 'ultramsg' | 'callmebot' | 'meta' | 'aisensy'
    WA_PROVIDER: str = os.getenv("WA_PROVIDER", "ultramsg")

    # AiSensy — one campaign name per automated template (Daily Entry,
    # Bridal, Clients, Inquiry, scheduled reminders). Each of these is a
    # SEPARATE AiSensy Campaign/Template (AiSensy is one-campaign-per-
    # template, no mixing) — set once each is approved and live.
    # Reuses WA_TOKEN as the AiSensy API key and the AISENSY_URL constant
    # already in whatsapp_service.py as the endpoint — no separate API
    # key/URL setting needed, since it's the same AiSensy account and a
    # fixed endpoint either way.
    AISENSY_CAMPAIGN_DAILY_ENTRY: str = os.getenv("AISENSY_CAMPAIGN_DAILY_ENTRY", "")
    AISENSY_CAMPAIGN_DAILY_ENTRY_PDF: str = os.getenv("AISENSY_CAMPAIGN_DAILY_ENTRY_PDF", "")
    AISENSY_CAMPAIGN_EXCLUSIVE_POINTS: str = os.getenv("AISENSY_CAMPAIGN_EXCLUSIVE_POINTS", "")
    AISENSY_CAMPAIGN_BRIDAL_BRIDE: str = os.getenv("AISENSY_CAMPAIGN_BRIDAL_BRIDE", "")
    AISENSY_CAMPAIGN_BRIDAL_GROOM: str = os.getenv("AISENSY_CAMPAIGN_BRIDAL_GROOM", "")
    AISENSY_CAMPAIGN_BRIDAL_SIDER: str = os.getenv("AISENSY_CAMPAIGN_BRIDAL_SIDER", "")
    # Document-type templates for the "Send with PDF" button — separate from
    # the plain-text confirmation ones above, since a WhatsApp template must
    # be specifically approved with a File/Document header to carry a PDF
    # attachment; the confirmation templates weren't approved that way.
    AISENSY_CAMPAIGN_BRIDAL_BRIDE_PDF: str = os.getenv("AISENSY_CAMPAIGN_BRIDAL_BRIDE_PDF", "")
    AISENSY_CAMPAIGN_BRIDAL_GROOM_PDF: str = os.getenv("AISENSY_CAMPAIGN_BRIDAL_GROOM_PDF", "")
    AISENSY_CAMPAIGN_BRIDAL_SIDER_PDF: str = os.getenv("AISENSY_CAMPAIGN_BRIDAL_SIDER_PDF", "")
    AISENSY_CAMPAIGN_CLIENT_UPDATE: str = os.getenv("AISENSY_CAMPAIGN_CLIENT_UPDATE", "")
    AISENSY_CAMPAIGN_INQUIRY: str = os.getenv("AISENSY_CAMPAIGN_INQUIRY", "")
    AISENSY_CAMPAIGN_INQUIRY_PDF: str = os.getenv("AISENSY_CAMPAIGN_INQUIRY_PDF", "")
    AISENSY_CAMPAIGN_WINBACK: str = os.getenv("AISENSY_CAMPAIGN_WINBACK", "")
    AISENSY_CAMPAIGN_MEMBERSHIP: str = os.getenv("AISENSY_CAMPAIGN_MEMBERSHIP", "")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN: int = 10

    # PDF generation
    PDF_DIR: str = "/tmp/saundarya_pdfs"
    # Admin-uploaded static files (currently just the Inquiry service
    # booklet PDF) — NOT /tmp, since these are manually uploaded assets
    # with no way to regenerate them, and /tmp can be wiped on reboot.
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
