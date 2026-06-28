from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import User, Settings
from insta_agent.services.instagram_oauth import oauth_configured, oauth_status

bp = Blueprint("auth", __name__)

PUBLIC_ENDPOINTS = {
  "auth.login", "auth.register", "main.home", "main.privacy",
  "oauth.callback", "webhook.verify_webhook", "webhook.webhook",
  "media.serve_file", "static",
}


def user_has_connection(user: User) -> bool:
  try:
    if user.primary_ig_account:
      return True
    s = Settings.query.filter_by(user_id=user.id).first()
    return bool(s and s.access_token)
  except Exception:
    db.session.rollback()
    return False


def after_login_redirect():
  try:
    if user_has_connection(current_user):
      return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.onboarding"))
  except Exception:
    db.session.rollback()
    flash("خطای موقت سرور — لطفاً دوباره تلاش کن.", "error")
    return render_template("login.html"), 503


@bp.before_app_request
def require_ig_connection_for_panel():
  from flask import request
  if not current_user.is_authenticated:
    return
  ep = request.endpoint or ""
  if ep in PUBLIC_ENDPOINTS or ep.startswith("webhook."):
    return
  if ep in ("auth.logout", "auth.onboarding", "auth.pages", "oauth.connect", "oauth.disconnect", "settings.settings"):
    return
  try:
    if user_has_connection(current_user):
      return
  except Exception:
    db.session.rollback()
    return
  if ep != "auth.onboarding":
    return redirect(url_for("auth.onboarding"))


@bp.route("/login", methods=["GET", "POST"])
def login():
  try:
    if current_user.is_authenticated:
      return after_login_redirect()
    if request.method == "POST":
      username = request.form.get("username", "").strip()
      password = request.form.get("password", "")
      user = User.query.filter_by(username=username).first()
      if user and user.check_password(password):
        login_user(user, remember=bool(request.form.get("remember")))
        nxt = request.args.get("next")
        if nxt:
          return redirect(nxt)
        return after_login_redirect()
      flash("نام کاربری یا رمز عبور اشتباه است.", "error")
  except Exception:
    db.session.rollback()
    flash("خطای موقت سرور — چند ثانیه صبر کن و دوباره تلاش کن.", "error")
    return render_template("login.html"), 503
  return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
  if current_user.is_authenticated:
    return after_login_redirect()
  if request.method == "POST":
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    if len(username) < 3:
      flash("نام کاربری باید حداقل ۳ کاراکتر باشد.", "error")
    elif len(password) < 6:
      flash("رمز عبور باید حداقل ۶ کاراکتر باشد.", "error")
    elif password != confirm:
      flash("تکرار رمز مطابقت ندارد.", "error")
    elif User.query.filter_by(username=username).first():
      flash("این نام کاربری قبلاً ثبت شده.", "error")
    elif email and User.query.filter_by(email=email).first():
      flash("این ایمیل قبلاً ثبت شده.", "error")
    else:
      user = User(username=username, email=email)
      user.set_password(password)
      db.session.add(user)
      db.session.commit()
      login_user(user, remember=True)
      flash("حسابت ساخته شد! حالا پیج اینستاگرامت را وصل کن.", "success")
      return redirect(url_for("auth.onboarding"))
  return render_template("register.html")


@bp.route("/onboarding")
@login_required
def onboarding():
  if user_has_connection(current_user):
    return redirect(url_for("dashboard.dashboard"))
  return render_template("onboarding.html", oauth_ready=oauth_configured(), oauth=oauth_status())


@bp.route("/pages")
@login_required
def pages():
  from insta_agent.models import IgAccount
  from insta_agent.services.instagram_profile import sync_ig_account_profile, probe_me
  from insta_agent.services.instagram_webhooks import get_webhook_subscription

  accounts = IgAccount.query.filter_by(user_id=current_user.id).order_by(
    IgAccount.is_primary.desc(), IgAccount.connected_at.desc()
  ).all()

  needs_sync = [
    a for a in accounts
    if not a.profile_synced_at or (not a.profile_picture and not a.follower_count)
  ]
  for acc in needs_sync:
    sync_ig_account_profile(acc)
  if needs_sync:
    db.session.commit()

  webhook_subs = {}
  token_health = {}
  for acc in accounts:
    if acc.access_token:
      ok, err = probe_me(acc.access_token)
      token_health[acc.id] = {"ok": ok, "error": err}
      webhook_subs[acc.id] = get_webhook_subscription(acc.ig_user_id, acc.access_token)
    else:
      token_health[acc.id] = {"ok": False, "error": "no token"}
      webhook_subs[acc.id] = {"subscribed": False, "fields": [], "error": "no token"}

  return render_template(
    "pages.html",
    accounts=accounts,
    oauth_ready=oauth_configured(),
    webhook_subs=webhook_subs,
    token_health=token_health,
  )


@bp.route("/logout")
@login_required
def logout():
  logout_user()
  return redirect(url_for("auth.login"))
