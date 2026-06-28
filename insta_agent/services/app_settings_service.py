from insta_agent.config import Config
from insta_agent.extensions import db
from insta_agent.models.app_settings import AppSettings


def get_app_settings() -> AppSettings:
  s = db.session.get(AppSettings, 1)
  if not s:
    s = AppSettings(id=1)
    if Config.ZARINPAL_MERCHANT_ID:
      s.zarinpal_merchant_id = Config.ZARINPAL_MERCHANT_ID
      s.zarinpal_sandbox = Config.ZARINPAL_SANDBOX
    db.session.add(s)
    db.session.commit()
  return s


def zarinpal_merchant_id() -> str:
  env_id = (Config.ZARINPAL_MERCHANT_ID or "").strip()
  db_id = (get_app_settings().zarinpal_merchant_id or "").strip()
  return db_id or env_id


def zarinpal_sandbox_mode() -> bool:
  s = get_app_settings()
  if s.zarinpal_merchant_id:
    return bool(s.zarinpal_sandbox)
  return Config.ZARINPAL_SANDBOX


def zarinpal_is_configured() -> bool:
  return bool(zarinpal_merchant_id())
