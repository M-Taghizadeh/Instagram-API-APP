from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class ActivityLog(db.Model):
  __tablename__ = "activity_logs"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  rule_type = db.Column(db.String(20), default="dm")
  rule_id = db.Column(db.String(36), default="")
  rule_name = db.Column(db.String(200), default="")
  ig_user_id = db.Column(db.String(100), default="")
  ig_username = db.Column(db.String(100), default="")
  action = db.Column(db.String(50), default="sent_dm")
  status = db.Column(db.String(20), default="ok")
  note = db.Column(db.Text, default="")
  created_at = db.Column(db.DateTime, default=now_tehran)


class CooldownEntry(db.Model):
  __tablename__ = "cooldown_entries"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  rule_id = db.Column(db.String(36), nullable=False)
  ig_user_id = db.Column(db.String(100), nullable=False)
  last_fired = db.Column(db.DateTime, default=now_tehran)


class WebhookMessage(db.Model):
  """Processed Instagram message ids — prevents duplicate webhook handling across workers."""
  __tablename__ = "webhook_messages"
  mid = db.Column(db.String(200), primary_key=True)
  created_at = db.Column(db.DateTime, default=now_tehran)
