import os

from flask import Flask, render_template
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

from insta_agent.config import Config
from insta_agent.extensions import db, login_manager
from insta_agent.models import User
from insta_agent.routes import ALL_BLUEPRINTS
from insta_agent.db_init import init_db
from insta_agent.services.scheduler_service import start_scheduler


def create_app():
  load_dotenv()
  app = Flask(__name__, template_folder="../templates", static_folder="../static")
  app.config.from_object(Config)
  app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

  db.init_app(app)
  login_manager.init_app(app)

  @app.teardown_appcontext
  def _rollback_on_error(exc):
    if exc is not None:
      db.session.rollback()

  @login_manager.user_loader
  def load_user(user_id):
    try:
      return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
      return None

  for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)

  init_db(app)
  start_scheduler(app)

  @app.errorhandler(500)
  def internal_error(err):
    db.session.rollback()
    app.logger.exception("Internal server error: %s", err)
    return (
      render_template(
        "error.html",
        code=500,
        title="خطای سرور",
        message="مشکلی موقت پیش آمد. چند ثانیه صبر کن و دوباره تلاش کن. اگر ادامه داشت، بعداً امتحان کن.",
        show_login=True,
      ),
      500,
    )

  @app.errorhandler(503)
  def service_unavailable(err):
    db.session.rollback()
    return (
      render_template(
        "error.html",
        code=503,
        title="سرور شلوغ است",
        message="الان نتوانستیم درخواست را کامل کنیم. لطفاً چند ثانیه بعد دوباره تلاش کن.",
        show_login=True,
      ),
      503,
    )

  @app.context_processor
  def inject_globals():
    from flask_login import current_user
    from insta_agent.services.subscription_service import subscription_status, subscription_banner
    from insta_agent.utils import JALALI_MONTH_NAMES
    sub_info = None
    sub_banner = None
    if current_user.is_authenticated:
      try:
        sub_info = subscription_status(current_user.id)
        sub_banner = subscription_banner(current_user.id)
      except Exception:
        pass
    return dict(sub_info=sub_info, sub_banner=sub_banner, jalali_month_names=JALALI_MONTH_NAMES)

  @app.template_filter("jalali")
  def jalali_filter(dt, fmt="%Y/%m/%d"):
    from insta_agent.utils import format_jalali
    return format_jalali(dt, fmt)

  return app
