from insta_agent.extensions import db
from insta_agent.utils import now_tehran


class Plan(db.Model):
  """پلن اشتراک بر اساس فالوور"""
  __tablename__ = "plans"
  id = db.Column(db.Integer, primary_key=True)
  slug = db.Column(db.String(20), unique=True, nullable=False)
  name = db.Column(db.String(50), nullable=False)
  follower_min = db.Column(db.Integer, default=0)
  follower_max = db.Column(db.Integer, default=10000)
  price_1m = db.Column(db.Integer, default=0)
  price_6m = db.Column(db.Integer, default=0)
  price_12m = db.Column(db.Integer, default=0)
  sort_order = db.Column(db.Integer, default=0)
  is_active = db.Column(db.Boolean, default=True)
  updated_at = db.Column(db.DateTime, default=now_tehran, onupdate=now_tehran)

  def price_for_period(self, months: int) -> int:
    if months == 1:
      return self.price_1m
    if months == 6:
      return self.price_6m
    if months == 12:
      return self.price_12m
    return self.price_1m * months

  def follower_label(self) -> str:
    labels = {
      "10k": "تا ۱۰K",
      "30k": "۱۰K – ۳۰K",
      "50k": "۳۰K – ۵۰K",
      "100k": "۵۰K – ۱۰۰K",
      "500k": "۱۰۰K – ۵۰۰K",
      "1m": "۵۰۰K – ۱M",
      "1m_plus": "بالای ۱M",
    }
    return labels.get(self.slug, f"{self.follower_min:,} – {self.follower_max:,}")


class Subscription(db.Model):
  __tablename__ = "subscriptions"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
  plan_slug = db.Column(db.String(20), default="trial")
  period_months = db.Column(db.Integer, default=0)
  is_trial = db.Column(db.Boolean, default=False)
  ig_user_id = db.Column(db.String(100), default="")
  status = db.Column(db.String(20), default="active")
  starts_at = db.Column(db.DateTime, default=now_tehran)
  expires_at = db.Column(db.DateTime, nullable=False)
  created_at = db.Column(db.DateTime, default=now_tehran)

  user = db.relationship("User", backref=db.backref("subscriptions", lazy=True))


class Payment(db.Model):
  __tablename__ = "payments"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
  plan_slug = db.Column(db.String(20), nullable=False)
  period_months = db.Column(db.Integer, default=1)
  amount_toman = db.Column(db.Integer, default=0)
  authority = db.Column(db.String(64), default="", index=True)
  ref_id = db.Column(db.String(64), default="")
  status = db.Column(db.String(20), default="pending")
  created_at = db.Column(db.DateTime, default=now_tehran)
  verified_at = db.Column(db.DateTime, nullable=True)

  user = db.relationship("User", backref=db.backref("payments", lazy=True))


class TrialUsage(db.Model):
  """جلوگیری از تکرار تریال — یک‌بار per کاربر و per پیج"""
  __tablename__ = "trial_usage"
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, unique=True, nullable=False)
  ig_user_id = db.Column(db.String(100), unique=True, nullable=False)
  used_at = db.Column(db.DateTime, default=now_tehran)
