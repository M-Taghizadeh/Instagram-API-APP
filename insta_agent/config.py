import os
import secrets

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
  SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

  _DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
  if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

  if not _DATABASE_URL:
    raise RuntimeError(
      "DATABASE_URL is required (PostgreSQL). "
      "Set it in Render environment variables or in your local .env file."
    )

  SQLALCHEMY_DATABASE_URI = _DATABASE_URL
  SQLALCHEMY_TRACK_MODIFICATIONS = False
  SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 180,
    "pool_size": 5,
    "max_overflow": 10,
    "connect_args": {
      "connect_timeout": 10,
      "keepalives": 1,
      "keepalives_idle": 30,
      "keepalives_interval": 10,
      "keepalives_count": 5,
    },
  }

  GRAPH_API = os.getenv("GRAPH_API", "https://graph.instagram.com/v25.0")
  PER_PAGE = 10
  COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3600"))

  # Instagram OAuth (Business Login)
  # Instagram OAuth — use IDs from Meta Dashboard → Instagram → API setup with Instagram login
  # (NOT the top-level "App ID" on the app homepage; those are often different numbers.)
  META_APP_ID = os.getenv("META_APP_ID", os.getenv("INSTAGRAM_APP_ID", ""))
  META_APP_SECRET = os.getenv("META_APP_SECRET", os.getenv("INSTAGRAM_APP_SECRET", ""))
  OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "")
  OAUTH_SCOPES = os.getenv(
    "OAUTH_SCOPES",
    "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments",
  )
  OAUTH_FORCE_REAUTH = os.getenv("OAUTH_FORCE_REAUTH", "false").lower() in ("1", "true", "yes")
  INSTAGRAM_LOGIN_URL = os.getenv("INSTAGRAM_LOGIN_URL", "https://www.instagram.com/")

  # Media uploads
  UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(_BASE, "uploads"))
  PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
  MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))

  # Scheduler
  SCHEDULER_INTERVAL_SEC = int(os.getenv("SCHEDULER_INTERVAL_SEC", "30"))

  # SMS defaults
  SMS_PROVIDER = os.getenv("SMS_PROVIDER", "kavenegar")

  MIGRATION_TOKEN = os.getenv("MIGRATION_TOKEN", "")
  VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")

  # Zarinpal
  ZARINPAL_MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID", "")
  ZARINPAL_SANDBOX = os.getenv("ZARINPAL_SANDBOX", "true").lower() in ("1", "true", "yes")
  TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))
