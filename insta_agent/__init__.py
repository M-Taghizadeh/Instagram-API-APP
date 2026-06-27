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
  app = Flask(__name__, template_folder="../templates")
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
  return app
