from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
  return render_template("index.html")


@bp.route("/academy")
def academy():
  return render_template("academy.html")


@bp.route("/about")
def about():
  return render_template("about.html")


@bp.route("/contact")
def contact():
  return render_template("contact.html")


@bp.route("/privacy")
def privacy():
  return (
    "<html><body style='font-family:sans-serif;padding:40px'>"
    "<h2>Privacy Policy</h2>"
    "<p>This app automates Instagram responses. No personal data is stored beyond what is needed.</p>"
    "</body></html>"
  )
