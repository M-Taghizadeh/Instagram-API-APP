from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class AppSettings(db.Model):
  """تنظیمات سراسری سامانه — فقط ادمین ویرایش می‌کند"""
  __tablename__ = "app_settings"
  id = db.Column(db.Integer, primary_key=True, default=1)
  zarinpal_merchant_id = db.Column(db.String(64), default="")
  zarinpal_sandbox = db.Column(db.Boolean, default=True)
  beta_tester_gate = db.Column(db.Boolean, default=True)
  trial_enabled = db.Column(db.Boolean, default=True)
  updated_at = db.Column(db.DateTime, default=now_tehran, onupdate=now_tehran)
