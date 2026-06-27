import os
import datetime

from flask_login import current_user

from insta_agent.config import Config
from insta_agent.extensions import db
from insta_agent.models import (
  User, Settings, ActivityLog, CooldownEntry,
)
from insta_agent.utils import now_tehran


def get_settings():
  if not current_user.is_authenticated:
    return Settings()
  s = Settings.query.filter_by(user_id=current_user.id).first()
  if not s:
    s = Settings(user_id=current_user.id, access_token="", verify_token="mysecret123")
    db.session.add(s)
    db.session.commit()
  return s


def get_settings_for(user_id: int):
  s = Settings.query.filter_by(user_id=user_id).first()
  if not s:
    s = Settings(user_id=user_id, access_token="", verify_token="mysecret123")
    db.session.add(s)
    db.session.commit()
  return s


def get_access_token(user_id: int) -> str:
  from insta_agent.models import IgAccount
  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  if ig and ig.access_token:
    return ig.access_token
  s = Settings.query.filter_by(user_id=user_id).first()
  return (s.access_token if s else "") or ""


def is_on_cooldown(user_id: int, rule_id: str, ig_user_id: str) -> bool:
  s = Settings.query.filter_by(user_id=user_id).first()
  if s and not s.cooldown_enabled:
    return False
  cooldown_secs = (s.cooldown_seconds if s and s.cooldown_seconds else None) or Config.COOLDOWN_SECONDS
  entry = CooldownEntry.query.filter_by(
    user_id=user_id, rule_id=rule_id, ig_user_id=ig_user_id
  ).first()
  if not entry:
    return False
  elapsed = (now_tehran() - entry.last_fired).total_seconds()
  return elapsed < cooldown_secs


def update_cooldown(user_id: int, rule_id: str, ig_user_id: str):
  entry = CooldownEntry.query.filter_by(
    user_id=user_id, rule_id=rule_id, ig_user_id=ig_user_id
  ).first()
  if entry:
    entry.last_fired = now_tehran()
  else:
    entry = CooldownEntry(user_id=user_id, rule_id=rule_id, ig_user_id=ig_user_id)
    db.session.add(entry)
  db.session.commit()


def log_activity(user_id, rule_type, rule_id, rule_name, ig_user_id, action,
                 status="ok", note="", ig_username=""):
  log = ActivityLog(
    user_id=user_id, rule_type=rule_type, rule_id=rule_id,
    rule_name=rule_name, ig_user_id=ig_user_id, ig_username=ig_username,
    action=action, status=status, note=note,
  )
  db.session.add(log)
  db.session.commit()


def _run_migrations():
  from sqlalchemy import text, inspect
  try:
    with db.engine.connect() as conn:
      inspector = inspect(db.engine)
      tables = inspector.get_table_names()

      if "activity_logs" in tables:
        existing = {c["name"] for c in inspector.get_columns("activity_logs")}
        if "ig_username" not in existing:
          conn.execute(text("ALTER TABLE activity_logs ADD COLUMN ig_username VARCHAR(100) DEFAULT ''"))

      if "settings" in tables:
        existing = {c["name"] for c in inspector.get_columns("settings")}
        for col, ddl in [
          ("cooldown_enabled", "ALTER TABLE settings ADD COLUMN cooldown_enabled BOOLEAN DEFAULT TRUE"),
          ("cooldown_seconds", "ALTER TABLE settings ADD COLUMN cooldown_seconds INTEGER DEFAULT 3600"),
        ]:
          if col not in existing:
            conn.execute(text(ddl))

      if "dm_rules" in tables:
        existing = {c["name"] for c in inspector.get_columns("dm_rules")}
        for col, ddl in [
          ("is_active", "ALTER TABLE dm_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
          ("fire_count", "ALTER TABLE dm_rules ADD COLUMN fire_count INTEGER DEFAULT 0"),
        ]:
          if col not in existing:
            conn.execute(text(ddl))

      if "comment_rules" in tables:
        existing = {c["name"] for c in inspector.get_columns("comment_rules")}
        for col, ddl in [
          ("is_active", "ALTER TABLE comment_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
          ("fire_count", "ALTER TABLE comment_rules ADD COLUMN fire_count INTEGER DEFAULT 0"),
          ("post_caption", "ALTER TABLE comment_rules ADD COLUMN post_caption TEXT DEFAULT ''"),
          ("post_thumb", "ALTER TABLE comment_rules ADD COLUMN post_thumb TEXT DEFAULT ''"),
        ]:
          if col not in existing:
            conn.execute(text(ddl))

      if "users" in tables:
        existing = {c["name"] for c in inspector.get_columns("users")}
        if "email" not in existing:
          conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(120) DEFAULT ''"))
        if "created_at" not in existing:
          conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))

      conn.commit()
    print("[MIGRATE] done", flush=True)
  except Exception as e:
    print(f"[MIGRATE] ERROR: {e}", flush=True)


def init_db(app):
  with app.app_context():
    db.create_all()
    _run_migrations()
    if not User.query.first():
      admin_user = os.getenv("ADMIN_USERNAME", "admin")
      admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
      u = User(username=admin_user)
      u.set_password(admin_pass)
      db.session.add(u)
      db.session.commit()
      print(f"[INIT] Admin created → {admin_user}", flush=True)

    upload_dir = app.config.get("UPLOAD_DIR")
    if upload_dir:
      os.makedirs(upload_dir, exist_ok=True)
