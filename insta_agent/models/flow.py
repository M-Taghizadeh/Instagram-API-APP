import uuid

from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class Flow(db.Model):
  """فلو اتومیشن — جایگزین/مکمل قوانین ساده"""
  __tablename__ = "flows"
  id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  name = db.Column(db.String(200), nullable=False)
  description = db.Column(db.Text, default="")
  channel = db.Column(db.String(20), default="dm")       # dm | comment | story
  flow_kind = db.Column(db.String(30), default="automation")  # automation | form | poll | quiz | showcase | followup
  trigger = db.Column(db.String(500), default="")
  match_type = db.Column(db.String(20), default="contains")
  post_id = db.Column(db.String(100), default="")        # برای کامنت روی پست خاص
  nodes_json = db.Column(db.Text, default="[]")
  is_active = db.Column(db.Boolean, default=True)
  fire_count = db.Column(db.Integer, default=0)
  created_at = db.Column(db.DateTime, default=now_tehran)
  updated_at = db.Column(db.DateTime, default=now_tehran, onupdate=now_tehran)


class FlowSession(db.Model):
  """جلسه فعال فلو برای هر کاربر اینستاگرام"""
  __tablename__ = "flow_sessions"
  id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  flow_id = db.Column(db.String(36), db.ForeignKey("flows.id"), nullable=False)
  ig_user_id = db.Column(db.String(100), nullable=False)
  ig_username = db.Column(db.String(100), default="")
  current_node_id = db.Column(db.String(50), default="")
  context_json = db.Column(db.Text, default="{}")
  status = db.Column(db.String(20), default="active")  # active | completed | expired
  updated_at = db.Column(db.DateTime, default=now_tehran, onupdate=now_tehran)
  created_at = db.Column(db.DateTime, default=now_tehran)

  flow = db.relationship("Flow", backref=db.backref("sessions", lazy=True))
