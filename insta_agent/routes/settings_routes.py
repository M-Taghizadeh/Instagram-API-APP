from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.db_init import get_settings
from insta_agent.services.instagram_oauth import oauth_configured
from insta_agent.services.app_settings_service import get_app_settings

bp = Blueprint("settings", __name__)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
  s = get_settings()
  ig = current_user.primary_ig_account
  app_cfg = get_app_settings()

  if request.method == "POST":
    form_type = request.form.get("form_type", "")

    if form_type == "zarinpal":
      if not current_user.is_admin:
        abort(403)
      app_cfg.zarinpal_merchant_id = request.form.get("zarinpal_merchant_id", "").strip()
      app_cfg.zarinpal_sandbox = request.form.get("zarinpal_sandbox") == "1"
      db.session.commit()
      flash("تنظیمات زرین‌پال ذخیره شد.", "success")
      return redirect(url_for("settings.settings"))

    if form_type == "cooldown":
      s.cooldown_enabled = request.form.get("cooldown_enabled") == "1"
      try:
        s.cooldown_seconds = max(0, int(request.form.get("cooldown_seconds", 3600)))
      except ValueError:
        s.cooldown_seconds = 3600
      db.session.commit()
      flash("تنظیمات Cooldown ذخیره شد.", "success")
      return redirect(url_for("settings.settings"))

    abort(403)

  return render_template(
    "settings.html",
    s=s,
    ig_account=ig,
    oauth_ready=oauth_configured(),
    app_cfg=app_cfg,
  )


@bp.route("/change-password", methods=["GET", "POST"])
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
      return redirect(url_for("settings.settings"))
  return render_template("change_password.html")
