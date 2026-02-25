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

    # App
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8080")
    APP_ENV: str = os.getenv("APP_ENV", "development")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
