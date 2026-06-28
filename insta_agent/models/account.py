from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class Settings(db.Model):
  __tablename__ = "settings"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  access_token = db.Column(db.Text, default="")
  verify_token = db.Column(db.String(120), default="mysecret123")
  cooldown_enabled = db.Column(db.Boolean, default=True)
  cooldown_seconds = db.Column(db.Integer, default=3600)


class IgAccount(db.Model):
  """پیج اینستاگرام متصل‌شده از طریق OAuth"""
  __tablename__ = "ig_accounts"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  ig_user_id = db.Column(db.String(100), unique=True, nullable=False)
  username = db.Column(db.String(100), default="")
  name = db.Column(db.String(200), default="")
  account_type = db.Column(db.String(50), default="")  # BUSINESS | MEDIA_CREATOR
  profile_picture = db.Column(db.Text, default="")
  follower_count = db.Column(db.Integer, default=0)
  access_token = db.Column(db.Text, default="")
  token_expires_at = db.Column(db.DateTime, nullable=True)
  is_primary = db.Column(db.Boolean, default=True)
  connected_at = db.Column(db.DateTime, default=now_tehran)
  updated_at = db.Column(db.DateTime, default=now_tehran, onupdate=now_tehran)

  def is_professional(self) -> bool:
    return self.account_type.upper() in ("BUSINESS", "MEDIA_CREATOR", "CREATOR")

  def sync_to_settings(self):
    """توکن OAuth را در Settings هم ذخیره کن (سازگاری با کد قدیمی)"""
    from insta_agent.models.user import User
    s = Settings.query.filter_by(user_id=self.user_id).first()
    if not s:
      s = Settings(user_id=self.user_id, verify_token="mysecret123")
      db.session.add(s)
    if self.is_primary:
      s.access_token = self.access_token
    db.session.commit()
