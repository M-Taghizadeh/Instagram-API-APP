from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
  if current_user.is_authenticated:
    return redirect(url_for("dashboard.dashboard"))
  return render_template("index.html")


@bp.route("/privacy")
def privacy():
  return (
    "<html><body style='font-family:sans-serif;padding:40px'>"
    "<h2>Privacy Policy</h2>"
    "<p>This app automates Instagram responses. No personal data is stored beyond what is needed.</p>"
    "</body></html>"
  )
