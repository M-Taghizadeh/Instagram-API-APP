import uuid

from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class DmRule(db.Model):
  __tablename__ = "dm_rules"
  id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  trigger = db.Column(db.String(500), nullable=False)
  response = db.Column(db.Text, nullable=False, default="")
  match_type = db.Column(db.String(20), default="contains")
  is_active = db.Column(db.Boolean, default=True)
  fire_count = db.Column(db.Integer, default=0)
  created_at = db.Column(db.DateTime, default=now_tehran)


class CommentRule(db.Model):
  __tablename__ = "comment_rules"
  id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  post_link = db.Column(db.Text, default="")
  post_id = db.Column(db.String(100), default="")
  post_caption = db.Column(db.Text, default="")
  post_thumb = db.Column(db.Text, default="")
  trigger = db.Column(db.String(500), nullable=False)
  match_type = db.Column(db.String(20), default="contains")
  comment_reply = db.Column(db.Text, default="")
  dm_response = db.Column(db.Text, default="")
  is_active = db.Column(db.Boolean, default=True)
  fire_count = db.Column(db.Integer, default=0)
  created_at = db.Column(db.DateTime, default=now_tehran)
