from sqlalchemy import event

from insta_agent.extensions import db


def configure_sqlite(app):
  uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
  if "sqlite" not in uri:
    return

  with app.app_context():

    @event.listens_for(db.engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA journal_mode=WAL")
      cursor.execute("PRAGMA busy_timeout=30000")
      cursor.execute("PRAGMA synchronous=NORMAL")
      cursor.close()
