from sqlalchemy.exc import IntegrityError

from insta_agent.config import Config
from insta_agent.extensions import db
from insta_agent.models.app_settings import AppSettings


def get_app_settings() -> AppSettings:
  s = db.session.get(AppSettings, 1)
  if s:
    return s
  s = AppSettings(id=1, beta_tester_gate=Config.BETA_TESTER_GATE)
  if Config.ZARINPAL_MERCHANT_ID:
    s.zarinpal_merchant_id = Config.ZARINPAL_MERCHANT_ID
    s.zarinpal_sandbox = Config.ZARINPAL_SANDBOX
  db.session.add(s)
  try:
    db.session.commit()
  except IntegrityError:
    db.session.rollback()
    s = db.session.get(AppSettings, 1)
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


def beta_tester_gate_enabled() -> bool:
  s = get_app_settings()
  if s.beta_tester_gate is None:
    return Config.BETA_TESTER_GATE
  return bool(s.beta_tester_gate)


def set_beta_tester_gate(enabled: bool) -> AppSettings:
  s = get_app_settings()
  s.beta_tester_gate = bool(enabled)
  db.session.commit()
  return s
