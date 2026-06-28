import datetime

from flask import Blueprint, redirect, url_for, request, flash, session
from flask_login import login_required, current_user, login_user

from insta_agent.extensions import db
from insta_agent.models import User, IgAccount, Settings
from insta_agent.services.instagram_oauth import (
  build_authorize_url, exchange_code_for_token, exchange_long_lived_token,
  get_me, is_professional_account, oauth_configured,
)
from insta_agent.services.subscription_service import maybe_start_trial

bp = Blueprint("oauth", __name__, url_prefix="/auth/instagram")


@bp.route("/connect")
@login_required
def connect():
  if not oauth_configured():
    flash("OAuth تنظیم نشده — META_APP_ID، META_APP_SECRET و OAUTH_REDIRECT_URI را در Render تنظیم کن.", "error")
    return redirect(url_for("auth.onboarding"))
  if not current_user.is_admin and IgAccount.query.filter_by(user_id=current_user.id).count() >= 1:
    flash("هر اشتراک فقط یک پیج دارد. برای تعویض، ابتدا پیج فعلی را قطع کن.", "error")
    return redirect(url_for("auth.pages"))
  state = str(current_user.id)
  session["oauth_state"] = state
  return redirect(build_authorize_url(state=state))


@bp.route("/callback")
def callback():
  code = request.args.get("code", "")
  state = request.args.get("state", "")
  error = request.args.get("error", "")
  error_desc = request.args.get("error_description", "")

  if error:
    flash(f"اتصال اینستاگرام لغو شد: {error_desc or error}", "error")
    return redirect(url_for("auth.onboarding") if current_user.is_authenticated else url_for("auth.login"))

  if not code:
    flash("کد احراز هویت دریافت نشد.", "error")
    return redirect(url_for("auth.login"))

  user = None
  if current_user.is_authenticated:
    user = current_user
  elif state and state.isdigit():
    user = db.session.get(User, int(state))

  if not user:
    flash("ابتدا ثبت‌نام کن یا وارد شو، بعد پیج اینستاگرام را وصل کن.", "error")
    return redirect(url_for("auth.register"))

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
      return redirect(url_for("auth.onboarding"))

    ig_id = str(profile.get("user_id") or ig_user_id)
    ig_username = profile.get("username", "") or f"ig_{ig_id[:8]}"
    follower_count = int(profile.get("followers_count") or 0)

    existing = IgAccount.query.filter_by(ig_user_id=ig_id).first()
    if existing and existing.user_id != user.id:
      flash("این پیج قبلاً به حساب دیگری متصل شده.", "error")
      return redirect(url_for("auth.pages"))

    has_other_page = IgAccount.query.filter(
      IgAccount.user_id == user.id,
      IgAccount.ig_user_id != ig_id,
    ).first()
    if has_other_page and not user.is_admin:
      flash("هر اشتراک فقط یک پیج دارد. ابتدا پیج فعلی را قطع کن.", "error")
      return redirect(url_for("auth.pages"))

    IgAccount.query.filter_by(user_id=user.id).update({"is_primary": False})

    if existing and existing.user_id == user.id:
      acc = existing
    else:
      acc = IgAccount(user_id=user.id, ig_user_id=ig_id)
      db.session.add(acc)

    acc.username = ig_username
    acc.name = profile.get("name", "")
    acc.account_type = account_type
    acc.profile_picture = profile.get("profile_picture_url", "")
    acc.follower_count = follower_count
    acc.access_token = access_token
    acc.token_expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    acc.is_primary = True
    acc.connected_at = datetime.datetime.utcnow()

    s = Settings.query.filter_by(user_id=user.id).first()
    if not s:
      s = Settings(user_id=user.id, verify_token=f"verify_{user.id}")
      db.session.add(s)
    s.access_token = access_token

    db.session.commit()

    trial = maybe_start_trial(user.id, ig_id)
    login_user(user, remember=True)
    if trial:
      flash(f"پیج @{ig_username} وصل شد — ۷ روز تریال رایگان فعال شد!", "success")
    else:
      flash(f"پیج @{ig_username} وصل شد و توکن به‌صورت خودکار ذخیره شد!", "success")
    return redirect(url_for("dashboard.dashboard"))

  except Exception as e:
    flash(f"خطا در اتصال اینستاگرام: {e}", "error")
    return redirect(url_for("auth.onboarding") if user else url_for("auth.login"))


@bp.route("/disconnect/<int:account_id>", methods=["POST"])
@login_required
def disconnect(account_id):
  acc = IgAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
  was_primary = acc.is_primary
  db.session.delete(acc)
  db.session.commit()

  if was_primary:
    s = Settings.query.filter_by(user_id=current_user.id).first()
    other = IgAccount.query.filter_by(user_id=current_user.id).first()
    if other:
      other.is_primary = True
      if s:
        s.access_token = other.access_token
    elif s:
      s.access_token = ""
    db.session.commit()

  flash("پیج قطع شد.", "success")
  return redirect(url_for("auth.pages"))


@bp.route("/disconnect")
@login_required
def disconnect_all():
  IgAccount.query.filter_by(user_id=current_user.id).delete()
  s = Settings.query.filter_by(user_id=current_user.id).first()
  if s:
    s.access_token = ""
  db.session.commit()
  flash("اتصال اینستاگرام قطع شد.", "success")
  return redirect(url_for("auth.onboarding"))
