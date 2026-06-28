import os
import datetime

from flask_login import current_user
from sqlalchemy.exc import IntegrityError

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
  if s:
    return s
  s = Settings(user_id=current_user.id, access_token="", verify_token="mysecret123")
  db.session.add(s)
  try:
    db.session.commit()
  except IntegrityError:
    db.session.rollback()
    s = Settings.query.filter_by(user_id=current_user.id).first()
  return s or Settings()


def get_settings_for(user_id: int):
  s = Settings.query.filter_by(user_id=user_id).first()
  if s:
    return s
  s = Settings(user_id=user_id, access_token="", verify_token="mysecret123")
  db.session.add(s)
  try:
    db.session.commit()
  except IntegrityError:
    db.session.rollback()
    s = Settings.query.filter_by(user_id=user_id).first()
  return s or Settings(user_id=user_id, access_token="", verify_token="mysecret123")


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

  def _add_column(conn, table: str, col: str, ddl: str):
    inspector = inspect(db.engine)
    if table not in inspector.get_table_names():
      return
    existing = {c["name"] for c in inspector.get_columns(table)}
    if col in existing:
      return
    conn.execute(text(ddl))
    conn.commit()
    print(f"[MIGRATE] {table}.{col} added", flush=True)

  try:
    with db.engine.connect() as conn:
      _add_column(conn, "activity_logs", "ig_username",
                  "ALTER TABLE activity_logs ADD COLUMN ig_username VARCHAR(100) DEFAULT ''")
      _add_column(conn, "settings", "cooldown_enabled",
                  "ALTER TABLE settings ADD COLUMN cooldown_enabled BOOLEAN DEFAULT TRUE")
      _add_column(conn, "settings", "cooldown_seconds",
                  "ALTER TABLE settings ADD COLUMN cooldown_seconds INTEGER DEFAULT 3600")
      _add_column(conn, "dm_rules", "is_active",
                  "ALTER TABLE dm_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
      _add_column(conn, "dm_rules", "fire_count",
                  "ALTER TABLE dm_rules ADD COLUMN fire_count INTEGER DEFAULT 0")
      _add_column(conn, "comment_rules", "is_active",
                  "ALTER TABLE comment_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
      _add_column(conn, "comment_rules", "fire_count",
                  "ALTER TABLE comment_rules ADD COLUMN fire_count INTEGER DEFAULT 0")
      _add_column(conn, "comment_rules", "post_caption",
                  "ALTER TABLE comment_rules ADD COLUMN post_caption TEXT DEFAULT ''")
      _add_column(conn, "comment_rules", "post_thumb",
                  "ALTER TABLE comment_rules ADD COLUMN post_thumb TEXT DEFAULT ''")
      _add_column(conn, "users", "email",
                  "ALTER TABLE users ADD COLUMN email VARCHAR(120) DEFAULT ''")
      _add_column(conn, "users", "created_at",
                  "ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
      _add_column(conn, "users", "is_admin",
                  "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
      _add_column(conn, "ig_accounts", "follower_count",
                  "ALTER TABLE ig_accounts ADD COLUMN follower_count INTEGER DEFAULT 0")

      # backfill nulls on existing rows
      for stmt in [
        "UPDATE dm_rules SET is_active=TRUE WHERE is_active IS NULL",
        "UPDATE dm_rules SET fire_count=0 WHERE fire_count IS NULL",
        "UPDATE comment_rules SET is_active=TRUE WHERE is_active IS NULL",
        "UPDATE comment_rules SET fire_count=0 WHERE fire_count IS NULL",
      ]:
        try:
          conn.execute(text(stmt))
          conn.commit()
        except Exception:
          conn.rollback()

    print("[MIGRATE] done", flush=True)
  except Exception as e:
    print(f"[MIGRATE] ERROR: {e}", flush=True)


DEFAULT_PLANS = [
  ("10k", "10K", 0, 10000, 179000, 890000, 1610000, 1),
  ("30k", "30K", 10001, 30000, 349000, 1740000, 3140000, 2),
  ("50k", "50K", 30001, 50000, 429000, 2140000, 3870000, 3),
  ("100k", "100K", 50001, 100000, 529000, 2645000, 4765000, 4),
  ("500k", "500K", 100001, 500000, 879000, 4385000, 7915000, 5),
  ("1m", "1M", 500001, 1000000, 1299000, 6485000, 11695000, 6),
  ("1m_plus", "1M+", 1000001, 999999999, 2199000, 10995000, 19795000, 7),
]


def _seed_plans():
  from insta_agent.models import Plan
  if Plan.query.first():
    return
  for slug, name, fmin, fmax, p1, p6, p12, order in DEFAULT_PLANS:
    db.session.add(Plan(
      slug=slug, name=name, follower_min=fmin, follower_max=fmax,
      price_1m=p1, price_6m=p6, price_12m=p12, sort_order=order,
    ))
  try:
    db.session.commit()
    print("[INIT] Plans seeded", flush=True)
  except IntegrityError:
    db.session.rollback()


def init_db(app):
  with app.app_context():
    print(f"[DB] {db.engine.dialect.name}", flush=True)
    db.create_all()
    _run_migrations()
    _seed_plans()
    from insta_agent.services.app_settings_service import get_app_settings
    get_app_settings()
    if not User.query.first():
      admin_user = os.getenv("ADMIN_USERNAME", "admin")
      admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
      u = User(username=admin_user, is_admin=True)
      u.set_password(admin_pass)
      db.session.add(u)
      db.session.commit()
      print(f"[INIT] Admin created -> {admin_user}", flush=True)
    else:
      first = User.query.order_by(User.id).first()
      if first and not User.query.filter_by(is_admin=True).first():
        first.is_admin = True
        db.session.commit()
        print(f"[INIT] Admin flag set -> {first.username}", flush=True)

    upload_dir = app.config.get("UPLOAD_DIR")
    if upload_dir:
      os.makedirs(upload_dir, exist_ok=True)
