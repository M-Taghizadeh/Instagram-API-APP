from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class Contact(db.Model):
  """CRM — اطلاعات جمع‌آوری‌شده از کاربران"""
  __tablename__ = "contacts"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  ig_user_id = db.Column(db.String(100), nullable=False)
  ig_username = db.Column(db.String(100), default="")
  phone = db.Column(db.String(30), default="")
  email = db.Column(db.String(120), default="")
  full_name = db.Column(db.String(200), default="")
  custom_fields_json = db.Column(db.Text, default="{}")
  source = db.Column(db.String(50), default="dm")  # dm | comment | form | manual
  tags = db.Column(db.String(500), default="")
  created_at = db.Column(db.DateTime, default=now_tehran)
  updated_at = db.Column(db.DateTime, default=now_tehran, onupdate=now_tehran)

  __table_args__ = (
    db.UniqueConstraint("user_id", "ig_user_id", name="uq_contact_user_ig"),
  )


class ScheduledMessage(db.Model):
  """فالوآپ و پیام زمان‌بندی‌شده"""
  __tablename__ = "scheduled_messages"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  ig_user_id = db.Column(db.String(100), nullable=False)
  ig_username = db.Column(db.String(100), default="")
  payload_json = db.Column(db.Text, nullable=False, default="{}")
  send_at = db.Column(db.DateTime, nullable=False)
  status = db.Column(db.String(20), default="pending")  # pending | sent | failed | cancelled
  note = db.Column(db.Text, default="")
  flow_id = db.Column(db.String(36), default="")
  created_at = db.Column(db.DateTime, default=now_tehran)
  sent_at = db.Column(db.DateTime, nullable=True)


class SmsConfig(db.Model):
  __tablename__ = "sms_configs"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
  provider = db.Column(db.String(30), default="kavenegar")
  api_key = db.Column(db.Text, default="")
  sender = db.Column(db.String(30), default="")
  is_active = db.Column(db.Boolean, default=False)


class SmsLog(db.Model):
  __tablename__ = "sms_logs"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  phone = db.Column(db.String(30), nullable=False)
  message = db.Column(db.Text, nullable=False)
  status = db.Column(db.String(20), default="pending")
  provider_response = db.Column(db.Text, default="")
  created_at = db.Column(db.DateTime, default=now_tehran)
