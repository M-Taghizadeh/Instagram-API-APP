from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class Notification(db.Model):
  __tablename__ = "notifications"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
  kind = db.Column(db.String(40), default="")
  title = db.Column(db.String(200), default="")
  body = db.Column(db.Text, default="")
  action_url = db.Column(db.String(500), default="")
  action_label = db.Column(db.String(120), default="")
  ig_username = db.Column(db.String(100), default="")
  read_at = db.Column(db.DateTime, nullable=True)
  created_at = db.Column(db.DateTime, default=now_tehran)

  user = db.relationship("User", backref=db.backref("notifications", lazy=True, cascade="all, delete-orphan"))

  @property
  def is_read(self) -> bool:
    return self.read_at is not None
