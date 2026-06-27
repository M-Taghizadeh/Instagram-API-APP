from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import ActivityLog, CooldownEntry
from insta_agent.db_init import get_settings
from insta_agent.services.instagram_oauth import oauth_configured

bp = Blueprint("settings", __name__)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
  s = get_settings()
  ig = current_user.primary_ig_account
  if request.method == "POST":
    s.access_token = request.form.get("access_token", "").strip()
    s.verify_token = request.form.get("verify_token", "").strip()
    s.cooldown_enabled = request.form.get("cooldown_enabled") == "1"
    try:
      s.cooldown_seconds = max(0, int(request.form.get("cooldown_seconds", 3600)))
    except ValueError:
      s.cooldown_seconds = 3600
    db.session.commit()
    flash("تنظیمات ذخیره شد.", "success")
    return redirect(url_for("settings.settings"))
  return render_template("settings.html", s=s, ig_account=ig, oauth_ready=oauth_configured())


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
