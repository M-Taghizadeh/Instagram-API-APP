import os

from flask import Flask
from dotenv import load_dotenv

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

  db.init_app(app)
  login_manager.init_app(app)

  @login_manager.user_loader
  def load_user(user_id):
    return db.session.get(User, int(user_id))

  for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)

  init_db(app)
  start_scheduler(app)

  @app.context_processor
  def inject_globals():
    from flask_login import current_user
    from insta_agent.services.subscription_service import subscription_status
    sub_info = None
    if current_user.is_authenticated:
      try:
        sub_info = subscription_status(current_user.id)
      except Exception:
        pass
    return dict(sub_info=sub_info)

  return app
