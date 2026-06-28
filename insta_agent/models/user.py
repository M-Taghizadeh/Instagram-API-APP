import hashlib
import secrets
import uuid

from flask_login import UserMixin

from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class User(UserMixin, db.Model):
  __tablename__ = "users"
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(80), unique=True, nullable=False)
  password_hash = db.Column(db.String(128), nullable=False)
  email = db.Column(db.String(120), default="")
  is_admin = db.Column(db.Boolean, default=False)
  created_at = db.Column(db.DateTime, default=now_tehran)

  dm_rules = db.relationship("DmRule", backref="owner", lazy=True, cascade="all, delete-orphan")
  comment_rules = db.relationship("CommentRule", backref="owner", lazy=True, cascade="all, delete-orphan")
  settings = db.relationship("Settings", backref="owner", lazy=True, uselist=False, cascade="all, delete-orphan")
  activity_logs = db.relationship("ActivityLog", backref="owner", lazy=True, cascade="all, delete-orphan")
  ig_accounts = db.relationship("IgAccount", backref="owner", lazy=True, cascade="all, delete-orphan")
  flows = db.relationship("Flow", backref="owner", lazy=True, cascade="all, delete-orphan")
  contacts = db.relationship("Contact", backref="owner", lazy=True, cascade="all, delete-orphan")

  def set_password(self, raw: str):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + raw).encode()).hexdigest()
    self.password_hash = f"{salt}${h}"

  def check_password(self, raw: str) -> bool:
    try:
      salt, h = self.password_hash.split("$")
      return hashlib.sha256((salt + raw).encode()).hexdigest() == h
    except Exception:
      return False

  @property
  def primary_ig_account(self):
    primary = [a for a in self.ig_accounts if a.is_primary]
    if primary:
      return primary[0]
    return self.ig_accounts[0] if self.ig_accounts else None
