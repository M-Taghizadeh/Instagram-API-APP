from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, flash
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user
)
import requests as http_requests
import os
import json
import uuid
import re
import hashlib
import secrets
import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

TEHRAN = ZoneInfo("Asia/Tehran")

def now_tehran():
    """زمان فعلی با تایم‌زون تهران"""
    return datetime.datetime.now(TEHRAN).replace(tzinfo=None)

# ========================= APP SETUP =========================
app = Flask(__name__)

_BASE = os.path.dirname(os.path.abspath(__file__))
_DATABASE_URL = os.getenv("DATABASE_URL", "")
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

if _DATABASE_URL:
    DB_URI = _DATABASE_URL
else:
    _DATA_DIR = os.getenv("DATA_DIR", _BASE)
    DB_PATH = os.path.join(_DATA_DIR, "app.db")
    DB_URI = f"sqlite:///{DB_PATH}"

app.config["SECRET_KEY"]                     = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"]        = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db            = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view    = "login"
login_manager.login_message = "برای دسترسی ابتدا وارد شو."

GRAPH_API = "https://graph.instagram.com/v25.0"
PER_PAGE  = 10
# مدت زمان cooldown بین دو پاسخ به یک کاربر (ثانیه) — قابل تنظیم با env var
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3600"))


# ========================= MODELS =========================
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    dm_rules      = db.relationship("DmRule",      backref="owner", lazy=True, cascade="all, delete-orphan")
    comment_rules = db.relationship("CommentRule", backref="owner", lazy=True, cascade="all, delete-orphan")
    settings      = db.relationship("Settings",    backref="owner", lazy=True, uselist=False, cascade="all, delete-orphan")
    activity_logs = db.relationship("ActivityLog", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw: str):
        salt = secrets.token_hex(16)
        h    = hashlib.sha256((salt + raw).encode()).hexdigest()
        self.password_hash = f"{salt}${h}"

    def check_password(self, raw: str) -> bool:
        try:
            salt, h = self.password_hash.split("$")
            return hashlib.sha256((salt + raw).encode()).hexdigest() == h
        except Exception:
            return False


class Settings(db.Model):
    __tablename__ = "settings"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    access_token    = db.Column(db.Text,        default="")
    verify_token    = db.Column(db.String(120), default="mysecret123")
    cooldown_enabled = db.Column(db.Boolean,   default=True)
    cooldown_seconds = db.Column(db.Integer,   default=3600)


class DmRule(db.Model):
    __tablename__ = "dm_rules"
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trigger    = db.Column(db.String(500), nullable=False)   # کلمات با ویرگول جدا می‌شن
    response   = db.Column(db.Text,        nullable=False, default="")
    match_type = db.Column(db.String(20),  default="contains")
    is_active  = db.Column(db.Boolean,     default=True)
    fire_count = db.Column(db.Integer,     default=0)        # تعداد دفعات اجرا
    created_at = db.Column(db.DateTime,    default=now_tehran)


class CommentRule(db.Model):
    __tablename__ = "comment_rules"
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_link     = db.Column(db.Text,        default="")
    post_id       = db.Column(db.String(100), default="")
    post_caption  = db.Column(db.Text,        default="")   # خلاصه کپشن برای نمایش
    post_thumb    = db.Column(db.Text,        default="")   # URL تصویر بندانگشتی
    trigger       = db.Column(db.String(500), nullable=False)  # کلمات با ویرگول جدا می‌شن
    match_type    = db.Column(db.String(20),  default="contains")
    comment_reply = db.Column(db.Text,        default="")
    dm_response   = db.Column(db.Text,        default="")
    is_active     = db.Column(db.Boolean,     default=True)
    fire_count    = db.Column(db.Integer,     default=0)
    created_at    = db.Column(db.DateTime,    default=now_tehran)


class ActivityLog(db.Model):
    """لاگ هر بار که یه قانون اجرا می‌شه"""
    __tablename__ = "activity_logs"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rule_type   = db.Column(db.String(20),  default="dm")
    rule_id     = db.Column(db.String(36),  default="")
    rule_name   = db.Column(db.String(200), default="")
    ig_user_id  = db.Column(db.String(100), default="")
    ig_username = db.Column(db.String(100), default="")   # @username اینستاگرام
    action      = db.Column(db.String(50),  default="sent_dm")
    status      = db.Column(db.String(20),  default="ok")
    note        = db.Column(db.Text,        default="")
    created_at  = db.Column(db.DateTime,    default=now_tehran)


class CooldownEntry(db.Model):
    """ردیابی آخرین پاسخ به هر کاربر برای هر قانون — جلوگیری از اسپم"""
    __tablename__ = "cooldown_entries"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rule_id    = db.Column(db.String(36), nullable=False)
    ig_user_id = db.Column(db.String(100), nullable=False)
    last_fired = db.Column(db.DateTime, default=now_tehran)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ========================= HELPERS =========================
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


def get_triggers(trigger_str: str) -> list:
    """کلمات کلیدی رو از یه رشته (با ویرگول/خط جدید جدا شده) جدا می‌کنه"""
    parts = re.split(r"[،,\n]+", trigger_str or "")
    return [p.strip() for p in parts if p.strip()]


def match_text(trigger_str: str, text: str, match_type: str = "contains") -> bool:
    """بررسی می‌کنه آیا متن با هر یک از کلمات کلیدی مطابقت داره"""
    if not text:
        return False
    text = text.lower().strip()
    for trigger in get_triggers(trigger_str):
        t = trigger.lower()
        if match_type == "exact":
            if t == text:
                return True
        else:
            if t in text:
                return True
    return False


def is_on_cooldown(user_id: int, rule_id: str, ig_user_id: str) -> bool:
    """بررسی می‌کنه آیا به این کاربر در بازه cooldown قبلاً پاسخ داده شده"""
    s = Settings.query.filter_by(user_id=user_id).first()
    if s and not s.cooldown_enabled:
        return False
    cooldown_secs = (s.cooldown_seconds if s and s.cooldown_seconds else None) or COOLDOWN_SECONDS
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


def log_activity(user_id: int, rule_type: str, rule_id: str, rule_name: str,
                 ig_user_id: str, action: str, status: str = "ok", note: str = "",
                 ig_username: str = ""):
    log = ActivityLog(
        user_id=user_id, rule_type=rule_type, rule_id=rule_id,
        rule_name=rule_name, ig_user_id=ig_user_id,
        ig_username=ig_username,
        action=action, status=status, note=note
    )
    db.session.add(log)
    db.session.commit()


def get_ig_username(ig_user_id: str, access_token: str) -> str:
    """username اینستاگرام رو از conversations API می‌گیره"""
    if not ig_user_id or not access_token:
        return ""
    try:
        r = http_requests.get(
            f"{GRAPH_API}/me/conversations",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "participants", "user_id": ig_user_id, "platform": "instagram"},
            timeout=8,
        )
        data = r.json()
        for conv in data.get("data", []):
            for p in conv.get("participants", {}).get("data", []):
                if p.get("id") == ig_user_id:
                    username = p.get("username", "")
                    print(f"[USERNAME] {ig_user_id} → @{username}", flush=True)
                    return username
    except Exception as e:
        print(f"[USERNAME] ERROR: {e}", flush=True)
    return ""


def resolve_post_id(post_link: str, access_token: str) -> str:
    """شناسه عددی پست رو از لینک پیدا می‌کنه — از /me/media برای مطابقت shortcode استفاده می‌کنه"""
    try:
        m = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", post_link or "")
        if not m or not access_token:
            return ""
        shortcode = m.group(1)
        # صفحه اول
        url = f"{GRAPH_API}/me/media"
        params = {"fields": "id,shortcode", "access_token": access_token, "limit": 100}
        while url:
            resp = http_requests.get(url, params=params, timeout=10)
            data = resp.json()
            for item in data.get("data", []):
                if item.get("shortcode") == shortcode:
                    print(f"[RESOLVE] found post_id={item['id']} for shortcode={shortcode}", flush=True)
                    return item["id"]
            # صفحه بعدی
            url = (data.get("paging") or {}).get("next")
            params = {}  # next URL کامله، param جداگانه نمی‌خواد
        print(f"[RESOLVE] shortcode={shortcode} not found in media list", flush=True)
        return ""
    except Exception as e:
        print("RESOLVE POST ID ERROR:", e)
        return ""


def get_post_preview(post_link: str, access_token: str) -> dict:
    """اطلاعات نمایشی پست (thumbnail, caption, permalink) رو برمی‌گردونه"""
    try:
        m = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", post_link or "")
        if not m or not access_token:
            return {}
        shortcode = m.group(1)
        url = f"{GRAPH_API}/me/media"
        params = {"fields": "id,shortcode,caption,thumbnail_url,media_url,media_type,permalink,timestamp", "access_token": access_token, "limit": 100}
        while url:
            resp = http_requests.get(url, params=params, timeout=10)
            data = resp.json()
            for item in data.get("data", []):
                if item.get("shortcode") == shortcode:
                    return {
                        "id":        item.get("id", ""),
                        "caption":   (item.get("caption") or "")[:120],
                        "image":     item.get("thumbnail_url") or item.get("media_url", ""),
                        "type":      item.get("media_type", ""),
                        "permalink": item.get("permalink", ""),
                        "timestamp": item.get("timestamp", ""),
                    }
            url = (data.get("paging") or {}).get("next")
            params = {}
        return {}
    except Exception as e:
        print("GET POST PREVIEW ERROR:", e)
        return {}


# ========================= INIT DB =========================
def _run_migrations():
    """اضافه کردن ستون‌های جدید به جداول موجود (idempotent — چندبار اجرا بی‌خطره)"""
    from sqlalchemy import text, inspect
    try:
        with db.engine.connect() as conn:
            inspector = inspect(db.engine)

            # ── activity_logs ──
            existing = {c["name"] for c in inspector.get_columns("activity_logs")}
            for col, ddl in [
                ("ig_username", "ALTER TABLE activity_logs ADD COLUMN ig_username VARCHAR(100) DEFAULT ''"),
            ]:
                if col not in existing:
                    conn.execute(text(ddl))
                    print(f"[MIGRATE] activity_logs.{col} added", flush=True)

            # ── settings ──
            existing = {c["name"] for c in inspector.get_columns("settings")}
            for col, ddl in [
                ("cooldown_enabled", "ALTER TABLE settings ADD COLUMN cooldown_enabled BOOLEAN DEFAULT TRUE"),
                ("cooldown_seconds", "ALTER TABLE settings ADD COLUMN cooldown_seconds INTEGER DEFAULT 3600"),
            ]:
                if col not in existing:
                    conn.execute(text(ddl))
                    print(f"[MIGRATE] settings.{col} added", flush=True)

            # ── dm_rules ──
            existing = {c["name"] for c in inspector.get_columns("dm_rules")}
            for col, ddl in [
                ("is_active",  "ALTER TABLE dm_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
                ("fire_count", "ALTER TABLE dm_rules ADD COLUMN fire_count INTEGER DEFAULT 0"),
            ]:
                if col not in existing:
                    conn.execute(text(ddl))
                    print(f"[MIGRATE] dm_rules.{col} added", flush=True)

            # ── comment_rules ──
            existing = {c["name"] for c in inspector.get_columns("comment_rules")}
            for col, ddl in [
                ("is_active",    "ALTER TABLE comment_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
                ("fire_count",   "ALTER TABLE comment_rules ADD COLUMN fire_count INTEGER DEFAULT 0"),
                ("post_caption", "ALTER TABLE comment_rules ADD COLUMN post_caption TEXT DEFAULT ''"),
                ("post_thumb",   "ALTER TABLE comment_rules ADD COLUMN post_thumb TEXT DEFAULT ''"),
            ]:
                if col not in existing:
                    conn.execute(text(ddl))
                    print(f"[MIGRATE] comment_rules.{col} added", flush=True)

            # backfill مقادیر null برای ردیف‌های قدیمی
            conn.execute(text("UPDATE dm_rules SET is_active=TRUE WHERE is_active IS NULL"))
            conn.execute(text("UPDATE dm_rules SET fire_count=0  WHERE fire_count IS NULL"))
            conn.execute(text("UPDATE comment_rules SET is_active=TRUE WHERE is_active IS NULL"))
            conn.execute(text("UPDATE comment_rules SET fire_count=0  WHERE fire_count IS NULL"))
            conn.commit()
        print("[MIGRATE] done", flush=True)
    except Exception as e:
        print(f"[MIGRATE] ERROR: {e}", flush=True)


def init_db():
    with app.app_context():
        db.create_all()        # جداول جدید (activity_logs, cooldown_entries)
        _run_migrations()      # ستون‌های جدید روی جداول قدیمی
        if not User.query.first():
            admin_user = os.getenv("ADMIN_USERNAME", "admin")
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
            u = User(username=admin_user)
            u.set_password(admin_pass)
            db.session.add(u)
            db.session.commit()
            print(f"[INIT] Admin created → {admin_user}")


# ========================= AUTH =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user     = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("نام کاربری یا رمز عبور اشتباه است.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ========================= WEBHOOK =========================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    incoming_token     = request.args.get("hub.verify_token", "")
    incoming_challenge = request.args.get("hub.challenge", "")
    verify_tok = os.getenv("VERIFY_TOKEN", "")
    if not verify_tok:
        first_user = User.query.first()
        if first_user:
            s = Settings.query.filter_by(user_id=first_user.id).first()
            if s:
                verify_tok = s.verify_token
    print(f"[WEBHOOK VERIFY] token={incoming_token!r} expected={verify_tok!r}")
    if incoming_token == verify_tok:
        print("[WEBHOOK VERIFY] OK →", incoming_challenge)
        return incoming_challenge, 200
    print("[WEBHOOK VERIFY] FAIL")
    return "fail", 403


# آخرین webhook payload رو در حافظه نگه می‌داره برای debug
_last_webhook_payload = []

@app.route("/debug/webhook")
@login_required
def debug_webhook():
    """نمایش آخرین ۵ webhook payload دریافت‌شده"""
    return jsonify(payloads=_last_webhook_payload)


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=True)
        print("\n===== WEBHOOK =====", flush=True)
        print(json.dumps(data, indent=2, ensure_ascii=False), flush=True)
        if not data:
            return jsonify(ok=True), 200

        # ذخیره برای debug
        _last_webhook_payload.append(data)
        if len(_last_webhook_payload) > 5:
            _last_webhook_payload.pop(0)

        for user in User.query.all():
            s         = get_settings_for(user.id)
            dm_rules  = DmRule.query.filter_by(user_id=user.id, is_active=True).all()
            com_rules = CommentRule.query.filter_by(user_id=user.id, is_active=True).all()

            for entry in data.get("entry", []):
                # DM — فرمت entry.messaging[]
                for event in entry.get("messaging", []):
                    _handle_messaging(event, dm_rules, s.access_token, user.id)

                # کامنت و سایر تغییرات — فرمت entry.changes[]
                for change in entry.get("changes", []):
                    field = change.get("field", "")
                    value = change.get("value", {})
                    print(f"[WEBHOOK] change.field={field!r}", flush=True)
                    if field == "comments":
                        _handle_comment(value, com_rules, s.access_token, user.id)
                    elif field in ("messages", "messaging"):
                        # بعضی نسخه‌های API پیام رو توی changes می‌فرستن
                        fake_event = {
                            "sender":  value.get("sender", {}),
                            "message": value.get("message", {}),
                        }
                        _handle_messaging(fake_event, dm_rules, s.access_token, user.id)

        return jsonify(ok=True), 200
    except Exception as e:
        import traceback
        print("WEBHOOK ERROR:", e, flush=True)
        print(traceback.format_exc(), flush=True)
        return jsonify(ok=False), 200


def _handle_messaging(event, dm_rules, token, owner_id):
    if "message" not in event:
        return
    sender_id = (event.get("sender") or {}).get("id")
    text      = (event.get("message") or {}).get("text", "")
    print(f"[DM] sender={sender_id} text={text!r} rules={len(dm_rules)}", flush=True)
    if not sender_id:
        return
    for rule in dm_rules:
        if match_text(rule.trigger, text, rule.match_type):
            if is_on_cooldown(owner_id, rule.id, sender_id):
                print(f"[DM] COOLDOWN — skipping rule {rule.id} for user {sender_id}", flush=True)
                break
            print(f"[DM] MATCH! sending to {sender_id}", flush=True)
            ok = _send_dm(sender_id, rule.response, token)
            rule.fire_count = (rule.fire_count or 0) + 1
            db.session.commit()
            update_cooldown(owner_id, rule.id, sender_id)
            username = get_ig_username(sender_id, token)
            log_activity(owner_id, "dm", rule.id, rule.trigger, sender_id,
                         "sent_dm", "ok" if ok else "error", ig_username=username)
            break


def _handle_comment(comment, rules, token, owner_id):
    text       = comment.get("text", "")
    media_id   = (comment.get("media") or {}).get("id")
    comment_id = comment.get("id")
    ig_user_id = (comment.get("from") or {}).get("id")
    for rule in rules:
        if rule.post_id and rule.post_id != media_id:
            continue
        if match_text(rule.trigger, text, rule.match_type):
            if is_on_cooldown(owner_id, rule.id, ig_user_id or ""):
                print(f"[COMMENT] COOLDOWN — skipping rule {rule.id}", flush=True)
                break
            actions = []
            if rule.comment_reply:
                ok = _reply_comment(comment_id, rule.comment_reply, token)
                if ok:
                    actions.append("replied_comment")
            if rule.dm_response:
                ok2 = _send_dm(ig_user_id, rule.dm_response, token)
                if ok2:
                    actions.append("sent_dm")
            rule.fire_count = (rule.fire_count or 0) + 1
            db.session.commit()
            if ig_user_id:
                update_cooldown(owner_id, rule.id, ig_user_id)
            action_str = "+".join(actions) if actions else "no_action"
            username = get_ig_username(ig_user_id, token) if ig_user_id else ""
            log_activity(owner_id, "comment", rule.id, rule.trigger,
                         ig_user_id or "", action_str, ig_username=username)
            break


def _send_dm(user_id, text, token) -> bool:
    if not user_id or not token:
        print(f"[SEND_DM] SKIP user_id={user_id} token_set={bool(token)}", flush=True)
        return False
    try:
        r = http_requests.post(
            f"{GRAPH_API}/me/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"recipient": {"id": user_id}, "message": {"text": text}},
            timeout=10,
        )
        print(f"[SEND_DM] status={r.status_code} response={r.text[:300]}", flush=True)
        return r.status_code == 200
    except Exception as e:
        print("DM ERROR:", e, flush=True)
        return False


def _reply_comment(comment_id, text, token) -> bool:
    if not comment_id or not token:
        return False
    try:
        r = http_requests.post(
            f"{GRAPH_API}/{comment_id}/replies",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": text},
            timeout=10,
        )
        print(f"[REPLY_COMMENT] status={r.status_code} response={r.text[:300]}", flush=True)
        return r.status_code == 200
    except Exception as e:
        print("COMMENT REPLY ERROR:", e, flush=True)
        return False


# ========================= DASHBOARD =========================
@app.route("/")
@login_required
def dashboard():
    dm_count      = DmRule.query.filter_by(user_id=current_user.id).count()
    comment_count = CommentRule.query.filter_by(user_id=current_user.id).count()
    dm_active     = DmRule.query.filter_by(user_id=current_user.id, is_active=True).count()
    cm_active     = CommentRule.query.filter_by(user_id=current_user.id, is_active=True).count()
    s             = get_settings()
    token_set     = bool(s.access_token)
    recent_dm     = DmRule.query.filter_by(user_id=current_user.id).order_by(DmRule.created_at.desc()).limit(3).all()
    recent_cm     = CommentRule.query.filter_by(user_id=current_user.id).order_by(CommentRule.created_at.desc()).limit(3).all()

    # آمار فعالیت ۷ روز اخیر
    seven_days_ago = now_tehran() - datetime.timedelta(days=7)
    total_fires    = ActivityLog.query.filter(
        ActivityLog.user_id == current_user.id,
        ActivityLog.created_at >= seven_days_ago
    ).count()
    recent_logs = ActivityLog.query.filter_by(user_id=current_user.id)\
        .order_by(ActivityLog.created_at.desc()).limit(5).all()

    # داده‌های نمودار ۷ روز اخیر
    chart_labels = []
    chart_data   = []
    for i in range(6, -1, -1):
        day = now_tehran() - datetime.timedelta(days=i)
        label = f"{day.month}/{day.day}"
        count = ActivityLog.query.filter(
            ActivityLog.user_id == current_user.id,
            ActivityLog.created_at >= day.replace(hour=0, minute=0, second=0),
            ActivityLog.created_at < day.replace(hour=23, minute=59, second=59),
        ).count()
        chart_labels.append(label)
        chart_data.append(count)

    return render_template("dashboard.html",
        dm_count=dm_count, comment_count=comment_count,
        dm_active=dm_active, cm_active=cm_active,
        token_set=token_set, recent_dm=recent_dm, recent_cm=recent_cm,
        webhook_url=request.url_root + "webhook",
        total_fires=total_fires, recent_logs=recent_logs,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),
    )


# ========================= DM RULES =========================
@app.route("/dm-rules")
@login_required
def dm_rules():
    q      = request.args.get("q", "").strip()
    page   = request.args.get("page", 1, type=int)
    query  = DmRule.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(DmRule.trigger.ilike(f"%{q}%") | DmRule.response.ilike(f"%{q}%"))
    pagination = query.order_by(DmRule.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("dm_rules.html", pagination=pagination, q=q)


@app.route("/dm-rule/new", methods=["GET", "POST"])
@login_required
def new_dm_rule():
    if request.method == "POST":
        rule = DmRule(
            user_id    = current_user.id,
            trigger    = request.form.get("trigger", "").strip(),
            response   = request.form.get("response", "").strip(),
            match_type = request.form.get("match_type", "contains"),
            is_active  = True,
        )
        db.session.add(rule)
        db.session.commit()
        flash("قانون دایرکت ساخته شد.", "success")
        return redirect(url_for("dm_rules"))
    return render_template("dm_rule_form.html", rule=None)


@app.route("/dm-rule/<rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_dm_rule(rule_id):
    rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        rule.trigger    = request.form.get("trigger", "").strip()
        rule.response   = request.form.get("response", "").strip()
        rule.match_type = request.form.get("match_type", "contains")
        db.session.commit()
        flash("قانون ویرایش شد.", "success")
        return redirect(url_for("dm_rules"))
    return render_template("dm_rule_form.html", rule=rule)


@app.route("/dm-rule/<rule_id>/toggle", methods=["POST"])
@login_required
def toggle_dm_rule(rule_id):
    rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    rule.is_active = not rule.is_active
    db.session.commit()
    return jsonify(active=rule.is_active)


@app.route("/dm-rule/<rule_id>/delete", methods=["POST"])
@login_required
def delete_dm_rule(rule_id):
    rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash("قانون حذف شد.", "success")
    return redirect(url_for("dm_rules"))


# ========================= POST PREVIEW API =========================
@app.route("/api/post-preview")
@login_required
def api_post_preview():
    """پیش‌نمایش پست اینستاگرام از لینک — برای فرم قانون کامنت"""
    link = request.args.get("link", "").strip()
    if not link:
        return jsonify(error="لینک وارد نشده"), 400
    s = get_settings()
    if not s.access_token:
        return jsonify(error="توکن دسترسی تنظیم نشده"), 400
    preview = get_post_preview(link, s.access_token)
    if not preview:
        return jsonify(error="پست پیدا نشد — لینک یا توکن را بررسی کن"), 404
    return jsonify(preview)


@app.route("/api/refresh-post-thumbs", methods=["POST"])
@login_required
def api_refresh_post_thumbs():
    """برای قانون‌هایی که post_thumb خالی دارن، اطلاعات پست رو دوباره می‌گیره و ذخیره می‌کنه"""
    s = get_settings()
    if not s.access_token:
        return jsonify(updated=0)
    rules = CommentRule.query.filter_by(user_id=current_user.id).filter(
        (CommentRule.post_thumb == "") | (CommentRule.post_thumb == None),
        CommentRule.post_link != "",
        CommentRule.post_link != None,
    ).all()
    updated = 0
    for rule in rules:
        preview = get_post_preview(rule.post_link, s.access_token)
        if preview:
            rule.post_id      = preview.get("id", rule.post_id or "")
            rule.post_caption = preview.get("caption", "")
            rule.post_thumb   = preview.get("image", "")
            updated += 1
    if updated:
        db.session.commit()
    print(f"[REFRESH THUMBS] updated {updated} rules", flush=True)
    return jsonify(updated=updated)


# ========================= COMMENT RULES =========================
@app.route("/comment-rules")
@login_required
def comment_rules():
    q      = request.args.get("q", "").strip()
    page   = request.args.get("page", 1, type=int)
    query  = CommentRule.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(
            CommentRule.trigger.ilike(f"%{q}%") |
            CommentRule.comment_reply.ilike(f"%{q}%") |
            CommentRule.dm_response.ilike(f"%{q}%")
        )
    pagination = query.order_by(CommentRule.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("comment_rules.html", pagination=pagination, q=q)


@app.route("/comment-rule/new", methods=["GET", "POST"])
@login_required
def new_comment_rule():
    if request.method == "POST":
        post_link = request.form.get("post_link", "").strip()
        s         = get_settings()
        preview   = get_post_preview(post_link, s.access_token) if post_link else {}
        rule = CommentRule(
            user_id       = current_user.id,
            post_link     = post_link,
            post_id       = preview.get("id", ""),
            post_caption  = preview.get("caption", ""),
            post_thumb    = preview.get("image", ""),
            trigger       = request.form.get("trigger", "").strip(),
            match_type    = request.form.get("match_type", "contains"),
            comment_reply = request.form.get("comment_reply", "").strip(),
            dm_response   = request.form.get("dm_response", "").strip(),
            is_active     = True,
        )
        db.session.add(rule)
        db.session.commit()
        flash("قانون کامنت ساخته شد.", "success")
        return redirect(url_for("comment_rules"))
    return render_template("comment_rule_form.html", rule=None)


@app.route("/comment-rule/<rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_comment_rule(rule_id):
    rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        post_link = request.form.get("post_link", "").strip()
        if post_link != rule.post_link:
            s = get_settings()
            preview = get_post_preview(post_link, s.access_token) if post_link else {}
            rule.post_id      = preview.get("id", "")
            rule.post_caption = preview.get("caption", "")
            rule.post_thumb   = preview.get("image", "")
        rule.post_link     = post_link
        rule.trigger       = request.form.get("trigger", "").strip()
        rule.match_type    = request.form.get("match_type", "contains")
        rule.comment_reply = request.form.get("comment_reply", "").strip()
        rule.dm_response   = request.form.get("dm_response", "").strip()
        db.session.commit()
        flash("قانون ویرایش شد.", "success")
        return redirect(url_for("comment_rules"))
    return render_template("comment_rule_form.html", rule=rule)


@app.route("/comment-rule/<rule_id>/toggle", methods=["POST"])
@login_required
def toggle_comment_rule(rule_id):
    rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    rule.is_active = not rule.is_active
    db.session.commit()
    return jsonify(active=rule.is_active)


@app.route("/comment-rule/<rule_id>/delete", methods=["POST"])
@login_required
def delete_comment_rule(rule_id):
    rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash("قانون حذف شد.", "success")
    return redirect(url_for("comment_rules"))


# ========================= ACTIVITY LOG =========================
@app.route("/activity")
@login_required
def activity_log():
    page = request.args.get("page", 1, type=int)
    ftype = request.args.get("type", "")
    query = ActivityLog.query.filter_by(user_id=current_user.id)
    if ftype in ("dm", "comment"):
        query = query.filter_by(rule_type=ftype)
    pagination = query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    total = ActivityLog.query.filter_by(user_id=current_user.id).count()
    return render_template("activity_log.html", pagination=pagination, ftype=ftype, total=total)


@app.route("/activity/clear", methods=["POST"])
@login_required
def clear_activity():
    ActivityLog.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("لاگ‌ها پاک شدند.", "success")
    return redirect(url_for("activity_log"))


@app.route("/activity/clear-cooldowns", methods=["POST"])
@login_required
def clear_cooldowns():
    deleted = CooldownEntry.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash(f"کولداون‌ها پاک شدند ({deleted} ردیف).", "success")
    return redirect(url_for("activity_log"))


# ========================= SETTINGS =========================
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    s = get_settings()
    if request.method == "POST":
        s.access_token     = request.form.get("access_token", "").strip()
        s.verify_token     = request.form.get("verify_token", "").strip()
        s.cooldown_enabled = request.form.get("cooldown_enabled") == "1"
        try:
            s.cooldown_seconds = max(0, int(request.form.get("cooldown_seconds", 3600)))
        except ValueError:
            s.cooldown_seconds = 3600
        db.session.commit()
        flash("تنظیمات ذخیره شد.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", s=s)


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        cur = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        cfm = request.form.get("confirm_password", "")
        if not current_user.check_password(cur):
            flash("رمز فعلی اشتباه است.", "error")
        elif len(new) < 6:
            flash("رمز جدید باید حداقل ۶ کاراکتر باشد.", "error")
        elif new != cfm:
            flash("تکرار رمز مطابقت ندارد.", "error")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("رمز عبور تغییر کرد.", "success")
            return redirect(url_for("settings"))
    return render_template("change_password.html")


# ========================= MIGRATION =========================
_MIGRATION_TOKEN = os.getenv("MIGRATION_TOKEN", "")

@app.route("/run-migration")
def run_migration():
    """
    Migration یک‌بار مصرف برای اضافه کردن ستون‌های جدید به PostgreSQL روی Render.
    برای امنیت نیاز به query param ?token=<MIGRATION_TOKEN> داره.
    بعد از اجرای موفق این route رو از کد حذف کن.
    """
    token = request.args.get("token", "")
    if not _MIGRATION_TOKEN or token != _MIGRATION_TOKEN:
        return jsonify(error="Unauthorized"), 403

    from sqlalchemy import text, inspect
    results = []

    try:
        with db.engine.connect() as conn:
            inspector = inspect(db.engine)

            # ── dm_rules ──
            existing_dm = [c["name"] for c in inspector.get_columns("dm_rules")]
            for col, ddl in [
                ("is_active",  "ALTER TABLE dm_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
                ("fire_count", "ALTER TABLE dm_rules ADD COLUMN fire_count INTEGER DEFAULT 0"),
            ]:
                if col not in existing_dm:
                    conn.execute(text(ddl))
                    results.append(f"✓ dm_rules.{col} added")
                else:
                    results.append(f"— dm_rules.{col} already exists")

            # ── comment_rules ──
            existing_cr = [c["name"] for c in inspector.get_columns("comment_rules")]
            for col, ddl in [
                ("is_active",    "ALTER TABLE comment_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
                ("fire_count",   "ALTER TABLE comment_rules ADD COLUMN fire_count INTEGER DEFAULT 0"),
                ("post_caption", "ALTER TABLE comment_rules ADD COLUMN post_caption TEXT DEFAULT ''"),
                ("post_thumb",   "ALTER TABLE comment_rules ADD COLUMN post_thumb TEXT DEFAULT ''"),
            ]:
                if col not in existing_cr:
                    conn.execute(text(ddl))
                    results.append(f"✓ comment_rules.{col} added")
                else:
                    results.append(f"— comment_rules.{col} already exists")

            # مقداردهی به ردیف‌های قدیمی
            conn.execute(text("UPDATE dm_rules SET is_active=TRUE WHERE is_active IS NULL"))
            conn.execute(text("UPDATE dm_rules SET fire_count=0 WHERE fire_count IS NULL"))
            conn.execute(text("UPDATE comment_rules SET is_active=TRUE WHERE is_active IS NULL"))
            conn.execute(text("UPDATE comment_rules SET fire_count=0 WHERE fire_count IS NULL"))
            conn.commit()
            results.append("✓ Existing rows backfilled")

        # ساخت جداول جدید (activity_logs, cooldown_entries)
        db.create_all()
        results.append("✓ New tables created (activity_logs, cooldown_entries)")

    except Exception as e:
        results.append(f"✕ ERROR: {e}")
        return jsonify(status="error", results=results), 500

    return jsonify(status="ok", results=results), 200


# ========================= MISC =========================
@app.route("/privacy")
def privacy():
    return ("<html><body style='font-family:sans-serif;padding:40px'>"
            "<h2>Privacy Policy</h2>"
            "<p>This app automates Instagram responses. No personal data is stored beyond what is needed.</p>"
            "</body></html>")


# ========================= RUN =========================
init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
