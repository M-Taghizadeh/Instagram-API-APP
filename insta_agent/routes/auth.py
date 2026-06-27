from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from insta_agent.models import User

from insta_agent.services.instagram_oauth import oauth_configured

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
  if current_user.is_authenticated:
    return redirect(url_for("dashboard.dashboard"))
  if request.method == "POST":
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
      login_user(user, remember=bool(request.form.get("remember")))
      return redirect(request.args.get("next") or url_for("dashboard.dashboard"))
    flash("نام کاربری یا رمز عبور اشتباه است.", "error")
  return render_template("login.html", oauth_ready=oauth_configured())


@bp.route("/logout")
@login_required
def logout():
  logout_user()
  return redirect(url_for("auth.login"))
