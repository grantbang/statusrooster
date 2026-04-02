from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    # GCP
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "statusrooster")

    # Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-to-a-random-string")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 72

    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID_PRO: str = os.getenv("STRIPE_PRICE_ID_PRO", "")

    # SendGrid
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL: str = os.getenv("SENDGRID_FROM_EMAIL", "alerts@statusrooster.com")

    # Twilio
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")
    TWILIO_MESSAGING_SERVICE_SID: str = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")

    # OAuth — Google
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # OAuth — GitHub
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")

    # Data retention (days)
    FREE_DATA_RETENTION_DAYS: int = 30
    PRO_DATA_RETENTION_DAYS: int = 90

    # App
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8080")
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # Multi-region check workers
    WORKER_SECRET: str = os.getenv("WORKER_SECRET", "")
    WORKER_URL_US_EAST1: str = os.getenv("WORKER_URL_US_EAST1", "")  # Primary (empty = run locally)
    WORKER_URL_US_WEST1: str = os.getenv("WORKER_URL_US_WEST1", "")
    WORKER_URL_EU_WEST1: str = os.getenv("WORKER_URL_EU_WEST1", "")
    WORKER_URL_ASIA_EAST1: str = os.getenv("WORKER_URL_ASIA_EAST1", "")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()

_INSECURE_JWT_DEFAULT = "change-me-to-a-random-string"
if settings.is_production and (
    not settings.JWT_SECRET or settings.JWT_SECRET == _INSECURE_JWT_DEFAULT
):
    raise RuntimeError(
        "JWT_SECRET must be set to a strong random value in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
