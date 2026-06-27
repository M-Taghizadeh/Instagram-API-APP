import datetime
import secrets

from flask import Blueprint, redirect, url_for, request, flash, session
from flask_login import login_required, current_user, login_user

from insta_agent.extensions import db
from insta_agent.models import User, IgAccount, Settings
from insta_agent.services.instagram_oauth import (
  build_authorize_url, exchange_code_for_token, exchange_long_lived_token,
  get_me, is_professional_account, oauth_configured,
)

bp = Blueprint("oauth", __name__, url_prefix="/auth/instagram")


@bp.route("/connect")
def connect():
  if not oauth_configured():
    flash("OAuth تنظیم نشده — META_APP_ID، META_APP_SECRET و OAUTH_REDIRECT_URI را در .env وارد کن.", "error")
    return redirect(url_for("auth.login"))
  if current_user.is_authenticated:
    state = str(current_user.id)
  else:
    state = f"signup:{secrets.token_hex(8)}"
    session["oauth_signup_state"] = state
  session["oauth_state"] = state
  return redirect(build_authorize_url(state=state))


@bp.route("/callback")
def callback():
  code = request.args.get("code", "")
  state = request.args.get("state", "")
  error = request.args.get("error", "")
  error_desc = request.args.get("error_description", "")

  if error:
    flash(f"ورود اینستاگرام لغو شد: {error_desc or error}", "error")
    return redirect(url_for("auth.login"))

  if not code:
    flash("کد احراز هویت دریافت نشد.", "error")
    return redirect(url_for("auth.login"))

  user = None
  if current_user.is_authenticated:
    user = current_user
  elif state and state.isdigit():
    user = db.session.get(User, int(state))
  elif state.startswith("signup:"):
    if session.get("oauth_signup_state") != state:
      flash("نشست OAuth نامعتبر است. دوباره تلاش کن.", "error")
      return redirect(url_for("auth.login"))

  try:
    short = exchange_code_for_token(code)
    short_token = short.get("access_token", "")
    ig_user_id = str(short.get("user_id", ""))

    long = exchange_long_lived_token(short_token)
    access_token = long.get("access_token", short_token)
    expires_in = long.get("expires_in", 3600)

    profile = get_me(access_token)
    account_type = profile.get("account_type", "")

    if not is_professional_account(account_type):
      flash(
        "فقط حساب‌های Business یا Creator قابل اتصال هستند. "
        "در تنظیمات اینستاگرام حسابت را به Professional تبدیل کن.",
        "error",
      )
      return redirect(url_for("auth.login"))

    ig_id = str(profile.get("user_id") or ig_user_id)
    username = profile.get("username", "") or f"ig_{ig_id[:8]}"

    existing = IgAccount.query.filter_by(ig_user_id=ig_id).first()
    if existing:
      user = db.session.get(User, existing.user_id)
    elif not user:
      user = User.query.filter_by(username=username).first()
      if not user:
        user = User(username=username)
        user.set_password(secrets.token_hex(16))
        db.session.add(user)
        db.session.flush()

    if existing and existing.user_id != user.id:
      flash("این پیج قبلاً به حساب دیگری متصل شده.", "error")
      return redirect(url_for("auth.login"))

    IgAccount.query.filter_by(user_id=user.id).update({"is_primary": False})

    if existing:
      acc = existing
    else:
      acc = IgAccount(user_id=user.id, ig_user_id=ig_id)
      db.session.add(acc)

    acc.username = username
    acc.name = profile.get("name", "")
    acc.account_type = account_type
    acc.profile_picture = profile.get("profile_picture_url", "")
    acc.access_token = access_token
    acc.token_expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    acc.is_primary = True

    s = Settings.query.filter_by(user_id=user.id).first()
    if not s:
      s = Settings(user_id=user.id, verify_token="mysecret123")
      db.session.add(s)
    s.access_token = access_token

    user.username = username
    db.session.commit()

    session.pop("oauth_signup_state", None)
    login_user(user, remember=True)
    flash(f"پیج @{username} با موفقیت متصل شد!", "success")
    return redirect(url_for("dashboard.dashboard"))

  except Exception as e:
    flash(f"خطا در اتصال اینستاگرام: {e}", "error")
    return redirect(url_for("auth.login"))


@bp.route("/disconnect")
@login_required
def disconnect():
  IgAccount.query.filter_by(user_id=current_user.id).delete()
  s = Settings.query.filter_by(user_id=current_user.id).first()
  if s:
    s.access_token = ""
  db.session.commit()
  flash("اتصال اینستاگرام قطع شد.", "success")
  return redirect(url_for("settings.settings"))
