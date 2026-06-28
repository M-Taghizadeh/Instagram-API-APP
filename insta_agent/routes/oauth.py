import datetime

from flask import Blueprint, redirect, url_for, request, flash, session
from flask_login import login_required, current_user, login_user
from sqlalchemy.exc import DBAPIError, OperationalError

from insta_agent.config import Config
from insta_agent.extensions import db
from insta_agent.db_retry import db_retry, is_disconnect_error
from insta_agent.models import User, IgAccount, Settings
from insta_agent.services.instagram_oauth import (
  build_authorize_url, exchange_code_for_token, resolve_access_token,
  get_me_optional, is_professional_account, oauth_configured, oauth_status,
)
from insta_agent.services.instagram_profile import (
  sync_ig_account_profile, fetch_ig_profile, apply_profile_to_account,
  fetch_ig_profile_with_debug, debug_user_token, explain_profile_failure,
  token_health_report,
)
from insta_agent.services.subscription_service import maybe_start_trial
from insta_agent.services.instagram_webhooks import subscribe_instagram_webhooks

bp = Blueprint("oauth", __name__, url_prefix="/auth/instagram")
OAUTH_FLOW_VERSION = "2025-06-28d"


@bp.route("/status")
@login_required
def oauth_debug_status():
  if not current_user.is_admin:
    return {"error": "forbidden"}, 403
  st = oauth_status()
  ig = IgAccount.query.filter_by(user_id=current_user.id, is_primary=True).first()
  debug = {}
  if ig and ig.access_token:
    debug = token_health_report(ig.access_token)
    profile, err = fetch_ig_profile_with_debug(ig.access_token, ig.ig_user_id)
    debug["profile_ok"] = bool(profile)
    debug["profile_error"] = err
    debug["username"] = profile.get("username", "")
  return {
    "flow_version": OAUTH_FLOW_VERSION,
    "configured": st["ready"],
    "configured_app_id": Config.META_APP_ID,
    "app_id_set": st["app_id"],
    "secret_set": st["app_secret"],
    "redirect_uri": st["redirect_value"],
    "hint": (
      "META_APP_ID باید Instagram App ID از "
      "Instagram → API setup with Instagram login باشد (معمولاً با App ID بالای داشبورد فرق دارد)"
    ),
    "token_health": debug,
  }


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

  user_id = user.id
  user_is_admin = bool(user.is_admin)
  db.session.remove()

  try:
    short = exchange_code_for_token(code)
    short_token = short.get("access_token", "")
    ig_user_id = str(short.get("user_id", ""))
    if not short_token or not ig_user_id:
      raise ValueError("پاسخ اینستاگرام ناقص بود — توکن یا شناسه کاربر دریافت نشد.")

    access_token, expires_in = resolve_access_token(short_token)

    profile = get_me_optional(access_token, ig_user_id=ig_user_id)
    account_type = profile.get("account_type", "")

    if account_type and not is_professional_account(account_type):
      flash(
        "فقط حساب‌های Business یا Creator قابل اتصال هستند. "
        "در تنظیمات اینستاگرام حسابت را به Professional تبدیل کن.",
        "error",
      )
      return redirect(url_for("auth.onboarding"))

    ig_id = str(profile.get("user_id") or ig_user_id)
    ig_username = profile.get("username") or ""
    if not ig_username:
      ig_username = f"ig_{ig_id[:8]}" if ig_id else "instagram"

    stored_profile = profile
    if ig_username.startswith("ig_"):
      retry_profile = fetch_ig_profile(access_token, ig_id)
      if retry_profile.get("username"):
        stored_profile = retry_profile
        ig_username = retry_profile["username"]

  except Exception as e:
    if isinstance(e, (OperationalError, DBAPIError)) and is_disconnect_error(e):
      db.session.rollback()
      db.session.remove()
      flash("اتصال به دیتابیس موقتاً قطع شد — دوباره «اتصال پیج اینستاگرام» را بزن.", "error")
    else:
      flash(f"خطا در اتصال اینستاگرام: {e}", "error")
    return redirect(url_for("auth.onboarding"))

  try:
    def _persist_connection():
      user = db.session.get(User, user_id)
      if not user:
        raise ValueError("کاربر یافت نشد — دوباره وارد شو و اتصال را تکرار کن.")

      existing = IgAccount.query.filter_by(ig_user_id=ig_id).first()
      if existing and existing.user_id != user.id:
        raise ValueError("این پیج قبلاً به حساب دیگری متصل شده.")

      has_other_page = IgAccount.query.filter(
        IgAccount.user_id == user.id,
        IgAccount.ig_user_id != ig_id,
      ).first()
      if has_other_page and not user_is_admin:
        raise ValueError("هر اشتراک فقط یک پیج دارد. ابتدا پیج فعلی را قطع کن.")

      IgAccount.query.filter_by(user_id=user.id).update({"is_primary": False})

      if existing and existing.user_id == user.id:
        acc = existing
      else:
        acc = IgAccount(user_id=user.id, ig_user_id=ig_id)
        db.session.add(acc)

      acc.username = ig_username
      acc.access_token = access_token
      acc.token_expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
      acc.is_primary = True
      acc.connected_at = datetime.datetime.utcnow()

      apply_profile_to_account(acc, stored_profile)

      s = Settings.query.filter_by(user_id=user.id).first()
      if not s:
        s = Settings(user_id=user.id, verify_token=f"verify_{user.id}")
        db.session.add(s)
      s.access_token = access_token

      db.session.commit()
      trial = maybe_start_trial(user.id, ig_id)
      return user, acc, trial

    user, acc, trial = db_retry(_persist_connection)
    if acc.username and not acc.username.startswith("ig_"):
      ig_username = acc.username

    wh_ok, wh_err = subscribe_instagram_webhooks(ig_id, access_token)
    login_user(user, remember=True)
    if trial:
      flash(f"پیج @{ig_username} وصل شد — ۷ روز تریال رایگان فعال شد!", "success")
    else:
      flash(f"پیج @{ig_username} وصل شد و توکن به‌صورت خودکار ذخیره شد!", "success")
    if not wh_ok:
      flash(
        f"ثبت Webhook برای @{ig_username} ناموفق بود: {wh_err} — "
        "از صفحه «اتصال به اینستاگرام» دوباره «فعال‌سازی Webhook» را بزن.",
        "error",
      )
    if ig_username.startswith("ig_"):
      flash(
        "یوزرنیم واقعی پیج هنوز دریافت نشده — احتمالاً توکن کوتاه‌مدت بود. "
        "از صفحه «اتصال به اینستاگرام» دوباره «اتصال مجدد» بزن.",
        "error",
      )
    return redirect(url_for("dashboard.dashboard"))

  except ValueError as e:
    flash(str(e), "error")
    dest = url_for("auth.pages") if "پیج" in str(e) else url_for("auth.onboarding")
    return redirect(dest)
  except (OperationalError, DBAPIError) as e:
    db.session.rollback()
    db.session.remove()
    if is_disconnect_error(e):
      flash("اتصال به دیتابیس موقتاً قطع شد — دوباره «اتصال پیج اینستاگرام» را بزن.", "error")
    else:
      flash(f"خطای دیتابیس: {e}", "error")
    return redirect(url_for("auth.onboarding"))
  except Exception as e:
    db.session.rollback()
    flash(f"خطا در اتصال اینستاگرام: {e}", "error")
    return redirect(url_for("auth.onboarding"))


@bp.route("/refresh-profiles", methods=["POST"])
@login_required
def refresh_profiles():
  accounts = IgAccount.query.filter_by(user_id=current_user.id).all()
  updated = 0
  last_err = ""
  for acc in accounts:
    before = (acc.username, acc.follower_count, acc.media_count)
    profile, err = fetch_ig_profile_with_debug(acc.access_token or "", acc.ig_user_id)
    if profile:
      apply_profile_to_account(acc, profile)
    if err:
      last_err = err
    after = (acc.username, acc.follower_count, acc.media_count)
    if after != before or (acc.username and not acc.username.startswith("ig_")):
      updated += 1
  db.session.commit()
  if updated:
    flash(f"اطلاعات {updated} از {len(accounts)} پیج به‌روز شد.", "success")
  else:
    flash(explain_profile_failure(last_err, debug_user_token(accounts[0].access_token if accounts else "")), "error")
  return redirect(url_for("auth.pages"))


@bp.route("/subscribe-webhooks/<int:account_id>", methods=["POST"])
@login_required
def subscribe_webhooks(account_id):
  from insta_agent.services.instagram_profile import refresh_ig_access_token, probe_me

  acc = IgAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
  token = acc.access_token or ""
  if not token:
    flash("توکن پیج موجود نیست — دوباره وصل کن.", "error")
    return redirect(url_for("auth.pages"))

  ok, err = probe_me(token)
  if not ok:
    refreshed = refresh_ig_access_token(token)
    new_token = refreshed.get("access_token", "")
    if new_token:
      token = new_token
      acc.access_token = new_token
      s = Settings.query.filter_by(user_id=current_user.id).first()
      if s:
        s.access_token = new_token
      db.session.commit()
      ok, err = probe_me(token)

  if not ok:
    flash(f"توکن منقضی شده — ابتدا پیج را قطع کن و دوباره وصل کن. ({err})", "error")
    return redirect(url_for("auth.pages"))

  ok, err = subscribe_instagram_webhooks(acc.ig_user_id, token)
  if ok:
    flash(f"Webhook برای @{acc.username} فعال شد (messages, comments).", "success")
  else:
    flash(f"فعال‌سازی Webhook ناموفق: {err}", "error")
  return redirect(url_for("auth.pages"))


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
