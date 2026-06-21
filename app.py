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
from dotenv import load_dotenv

load_dotenv()

# ========================= APP SETUP =========================
app = Flask(__name__)

_BASE = os.path.dirname(os.path.abspath(__file__))
# اگه DATABASE_URL باشه (Render PostgreSQL) از اون استفاده می‌کنیم
# در غیر این صورت SQLite محلی
_DATABASE_URL = os.getenv("DATABASE_URL", "")
if _DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy نیاز به postgresql:// داره نه postgres://
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

GRAPH_API    = "https://graph.facebook.com/v21.0"
PER_PAGE     = 10


# ========================= MODELS =========================
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    dm_rules      = db.relationship("DmRule",      backref="owner", lazy=True, cascade="all, delete-orphan")
    comment_rules = db.relationship("CommentRule", backref="owner", lazy=True, cascade="all, delete-orphan")
    settings      = db.relationship("Settings",    backref="owner", lazy=True, uselist=False, cascade="all, delete-orphan")

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
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    access_token = db.Column(db.Text,        default="")
    verify_token = db.Column(db.String(120), default="mysecret123")


class DmRule(db.Model):
    __tablename__ = "dm_rules"
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trigger    = db.Column(db.String(200), nullable=False)
    response   = db.Column(db.Text,        nullable=False, default="")
    match_type = db.Column(db.String(20),  default="contains")
    created_at = db.Column(db.DateTime,    default=__import__("datetime").datetime.utcnow)


class CommentRule(db.Model):
    __tablename__ = "comment_rules"
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_link     = db.Column(db.Text,        default="")
    post_id       = db.Column(db.String(100), default="")
    trigger       = db.Column(db.String(200), nullable=False)
    match_type    = db.Column(db.String(20),  default="contains")
    comment_reply = db.Column(db.Text,        default="")
    dm_response   = db.Column(db.Text,        default="")
    created_at    = db.Column(db.DateTime,    default=__import__("datetime").datetime.utcnow)


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


def match_text(trigger: str, text: str, match_type: str = "contains") -> bool:
    if not text:
        return False
    trigger = trigger.lower().strip()
    text    = text.lower().strip()
    return trigger == text if match_type == "exact" else trigger in text


def resolve_post_id(post_link: str, access_token: str) -> str:
    try:
        m = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", post_link or "")
        if not m or not access_token:
            return ""
        resp = http_requests.get(
            f"{GRAPH_API}/ig_shortcode/{m.group(1)}",
            params={"fields": "id", "access_token": access_token},
            timeout=10,
        )
        return resp.json().get("id", "")
    except Exception as e:
        print("RESOLVE POST ID ERROR:", e)
        return ""


# ========================= INIT DB =========================
def init_db():
    with app.app_context():
        db.create_all()
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
    incoming_token    = request.args.get("hub.verify_token", "")
    incoming_challenge = request.args.get("hub.challenge", "")

    # اول env var، بعد دیتابیس
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


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=True)
        import sys
        print("\n===== WEBHOOK =====", flush=True)
        print(json.dumps(data, indent=2, ensure_ascii=False), flush=True)
        if not data:
            return jsonify(ok=True), 200

        for user in User.query.all():
            s         = get_settings_for(user.id)
            dm_rules  = DmRule.query.filter_by(user_id=user.id).all()
            com_rules = CommentRule.query.filter_by(user_id=user.id).all()

            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    _handle_messaging(event, dm_rules, s.access_token)
                for change in entry.get("changes", []):
                    if change.get("field") == "comments":
                        _handle_comment(change.get("value", {}), com_rules, s.access_token)

        return jsonify(ok=True), 200
    except Exception as e:
        print("WEBHOOK ERROR:", e, flush=True)
        return jsonify(ok=False), 200


def _handle_messaging(event, dm_rules, token):
    if "message" not in event:
        return
    sender_id = (event.get("sender") or {}).get("id")
    text      = (event.get("message") or {}).get("text", "")
    if not sender_id:
        return
    for rule in dm_rules:
        if match_text(rule.trigger, text, rule.match_type):
            _send_dm(sender_id, rule.response, token)
            break


def _handle_comment(comment, rules, token):
    text       = comment.get("text", "")
    media_id   = (comment.get("media") or {}).get("id")
    comment_id = comment.get("id")
    user_id    = (comment.get("from") or {}).get("id")
    for rule in rules:
        if rule.post_id and rule.post_id != media_id:
            continue
        if match_text(rule.trigger, text, rule.match_type):
            if rule.comment_reply:
                _reply_comment(comment_id, rule.comment_reply, token)
            if rule.dm_response:
                _send_dm(user_id, rule.dm_response, token)
            break


def _send_dm(user_id, text, token):
    if not user_id or not token:
        return
    try:
        http_requests.post(
            f"{GRAPH_API}/me/messages",
            params={"access_token": token},
            json={"recipient": {"id": user_id}, "message": {"text": text}},
            timeout=10,
        )
    except Exception as e:
        print("DM ERROR:", e)


def _reply_comment(comment_id, text, token):
    if not comment_id or not token:
        return
    try:
        http_requests.post(
            f"{GRAPH_API}/{comment_id}/replies",
            params={"access_token": token},
            data={"message": text},
            timeout=10,
        )
    except Exception as e:
        print("COMMENT REPLY ERROR:", e)


# ========================= DASHBOARD =========================
@app.route("/")
@login_required
def dashboard():
    dm_count      = DmRule.query.filter_by(user_id=current_user.id).count()
    comment_count = CommentRule.query.filter_by(user_id=current_user.id).count()
    s             = get_settings()
    token_set     = bool(s.access_token)
    recent_dm     = DmRule.query.filter_by(user_id=current_user.id).order_by(DmRule.created_at.desc()).limit(3).all()
    recent_cm     = CommentRule.query.filter_by(user_id=current_user.id).order_by(CommentRule.created_at.desc()).limit(3).all()
    return render_template("dashboard.html",
        dm_count=dm_count, comment_count=comment_count,
        token_set=token_set, recent_dm=recent_dm, recent_cm=recent_cm,
        webhook_url=request.url_root + "webhook"
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


@app.route("/dm-rule/<rule_id>/delete", methods=["POST"])
@login_required
def delete_dm_rule(rule_id):
    rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash("قانون حذف شد.", "success")
    return redirect(url_for("dm_rules"))


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
        post_id   = resolve_post_id(post_link, s.access_token)
        rule = CommentRule(
            user_id       = current_user.id,
            post_link     = post_link,
            post_id       = post_id,
            trigger       = request.form.get("trigger", "").strip(),
            match_type    = request.form.get("match_type", "contains"),
            comment_reply = request.form.get("comment_reply", "").strip(),
            dm_response   = request.form.get("dm_response", "").strip(),
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
            rule.post_id = resolve_post_id(post_link, s.access_token)
        rule.post_link     = post_link
        rule.trigger       = request.form.get("trigger", "").strip()
        rule.match_type    = request.form.get("match_type", "contains")
        rule.comment_reply = request.form.get("comment_reply", "").strip()
        rule.dm_response   = request.form.get("dm_response", "").strip()
        db.session.commit()
        flash("قانون ویرایش شد.", "success")
        return redirect(url_for("comment_rules"))
    return render_template("comment_rule_form.html", rule=rule)


@app.route("/comment-rule/<rule_id>/delete", methods=["POST"])
@login_required
def delete_comment_rule(rule_id):
    rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash("قانون حذف شد.", "success")
    return redirect(url_for("comment_rules"))


# ========================= SETTINGS =========================
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    s = get_settings()
    if request.method == "POST":
        s.access_token = request.form.get("access_token", "").strip()
        s.verify_token = request.form.get("verify_token", "").strip()
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
