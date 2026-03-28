import os
from dataclasses import dataclass


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MobileSettings:
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/dmk_logistic"),
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

    vapid_public_key: str = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    vapid_private_key: str = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    vapid_claim_email: str = os.getenv("VAPID_CLAIM_EMAIL", "mailto:admin@localhost").strip()

    mobile_upload_root: str = os.getenv("MOBILE_UPLOAD_ROOT", "data/mobile_point_uploads")

    bootstrap_demo_user: bool = _as_bool(os.getenv("BOOTSTRAP_DEMO_USER"), default=False)
    demo_login: str = os.getenv("DEMO_LOGIN", "driver")
    demo_password: str = os.getenv("DEMO_PASSWORD", "driver123")
    demo_role: str = os.getenv("DEMO_ROLE", "driver")


mobile_settings = MobileSettings()

