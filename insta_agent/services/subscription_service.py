import datetime

from insta_agent.config import Config
from insta_agent.extensions import db
from insta_agent.models import Plan, Subscription, Payment, TrialUsage, IgAccount, User
from insta_agent.utils import now_tehran

TRIAL_DAYS = Config.TRIAL_DAYS


def is_platform_admin(user_id: int) -> bool:
  user = db.session.get(User, user_id)
  return bool(user and user.is_admin)


def admin_subscription_status(user_id: int) -> dict:
  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  followers = ig.follower_count if ig else 0
  return {
    "active": True,
    "is_admin": True,
    "is_trial": False,
    "plan_slug": "admin",
    "plan_name": "مدیر سامانه",
    "expires_at": None,
    "days_left": 0,
    "followers": followers,
    "suggested_plan": plan_for_followers(followers),
    "trial_available": False,
    "label": "مدیر سامانه — دسترسی کامل",
  }


def get_plans(active_only: bool = True) -> list:
  q = Plan.query.order_by(Plan.sort_order)
  if active_only:
    q = q.filter_by(is_active=True)
  return q.all()


def get_plan(slug: str) -> Plan | None:
  return Plan.query.filter_by(slug=slug).first()


def plan_for_followers(count: int) -> Plan | None:
  count = max(0, count or 0)
  for p in get_plans():
    if p.follower_min <= count <= p.follower_max:
      return p
  return get_plan("1m_plus")


def get_active_subscription(user_id: int) -> Subscription | None:
  now = now_tehran()
  sub = Subscription.query.filter_by(user_id=user_id, status="active").order_by(
    Subscription.expires_at.desc()
  ).first()
  if not sub:
    return None
  if not sub.expires_at or sub.expires_at <= now:
    sub.status = "expired"
    try:
      db.session.commit()
    except Exception:
      db.session.rollback()
    return None
  return sub


def has_automation_access(user_id: int) -> bool:
  if is_platform_admin(user_id):
    return True
  return get_active_subscription(user_id) is not None


def expire_due_subscriptions():
  now = now_tehran()
  due = Subscription.query.filter(
    Subscription.status == "active",
    Subscription.expires_at <= now,
  ).all()
  for sub in due:
    sub.status = "expired"
  if due:
    db.session.commit()
  return len(due)


def _days_left(expires_at) -> int:
  delta = expires_at - now_tehran()
  return max(0, delta.days + (1 if delta.seconds > 0 else 0))


def subscription_status(user_id: int) -> dict:
  if is_platform_admin(user_id):
    return admin_subscription_status(user_id)

  sub = get_active_subscription(user_id)
  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  followers = ig.follower_count if ig else 0
  suggested = plan_for_followers(followers)

  if not sub:
    trial_used = TrialUsage.query.filter_by(user_id=user_id).first() is not None
    return {
      "active": False,
      "is_trial": False,
      "plan_slug": None,
      "plan_name": None,
      "expires_at": None,
      "days_left": 0,
      "followers": followers,
      "suggested_plan": suggested,
      "trial_available": not trial_used and ig is not None,
      "label": "بدون اشتراک فعال",
    }

  plan = get_plan(sub.plan_slug)
  name = "تریال ۷ روزه" if sub.is_trial else (plan.name if plan else sub.plan_slug)
  return {
    "active": True,
    "is_trial": sub.is_trial,
    "plan_slug": sub.plan_slug,
    "plan_name": name,
    "expires_at": sub.expires_at,
    "days_left": _days_left(sub.expires_at),
    "followers": followers,
    "suggested_plan": suggested,
    "trial_available": False,
    "label": f"{name} — {_days_left(sub.expires_at)} روز مانده",
  }


def subscription_banner(user_id: int) -> dict | None:
  if is_platform_admin(user_id):
    return None

  info = subscription_status(user_id)
  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  trial_record = TrialUsage.query.filter_by(user_id=user_id).first()

  if info["active"]:
    days = info["days_left"]
    if info["is_trial"]:
      message = (
        f"دوره آزمایشی رایگان — {days} روز از {TRIAL_DAYS} روز مانده"
        f" · پس از اتمام، همه امکانات تا انتخاب پلن غیرفعال می‌شود"
      )
      return {"message": message, "tone": "warn"}

    if days <= 14:
      message = f"اشتراک {info['plan_name']} فعال است · {days} روز تا پایان اشتراک"
      return {"message": message, "tone": "warn"}

    return None

  if not ig and not trial_record:
    message = (
      "اشتراک فعال نیست — در حال استفاده رایگان هستید"
      f" · با اتصال اولین پیج اینستاگرام، {TRIAL_DAYS} روز استفاده رایگان فعال می‌شود"
    )
    return {"message": message, "tone": "danger"}

  if trial_record:
    message = (
      f"اشتراک فعال نیست — دوره آزمایشی {TRIAL_DAYS} روزه تمام شده"
      " · همه امکانات غیرفعال است تا پلن اشتراک را انتخاب کنید"
    )
    return {"message": message, "tone": "danger"}

  message = "اشتراک فعال نیست — برای ادامه، اشتراک تهیه کنید"
  return {"message": message, "tone": "danger"}


def maybe_start_trial(user_id: int, ig_user_id: str) -> Subscription | None:
  if get_active_subscription(user_id):
    return None
  if TrialUsage.query.filter_by(user_id=user_id).first():
    return None
  if TrialUsage.query.filter_by(ig_user_id=ig_user_id).first():
    return None

  starts = now_tehran()
  expires = starts + datetime.timedelta(days=TRIAL_DAYS)
  sub = Subscription(
    user_id=user_id,
    plan_slug="trial",
    period_months=0,
    is_trial=True,
    ig_user_id=ig_user_id,
    status="active",
    starts_at=starts,
    expires_at=expires,
  )
  db.session.add(sub)
  db.session.add(TrialUsage(user_id=user_id, ig_user_id=ig_user_id))
  db.session.commit()
  return sub


def admin_deactivate_subscriptions(user_id: int) -> int:
  subs = Subscription.query.filter_by(user_id=user_id, status="active").all()
  for sub in subs:
    sub.status = "expired"
  if subs:
    db.session.commit()
  return len(subs)


def admin_grant_subscription(
  user_id: int,
  plan_slug: str,
  starts_at: datetime.datetime,
  expires_at: datetime.datetime,
  period_months: int = 1,
  is_trial: bool = False,
) -> Subscription:
  for sub in Subscription.query.filter_by(user_id=user_id, status="active").all():
    sub.status = "expired"

  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  sub = Subscription(
    user_id=user_id,
    plan_slug=plan_slug or "trial",
    period_months=period_months,
    is_trial=is_trial,
    ig_user_id=ig.ig_user_id if ig else "",
    status="active",
    starts_at=starts_at,
    expires_at=expires_at,
  )
  db.session.add(sub)
  db.session.commit()
  return sub


def activate_paid_subscription(
  user_id: int, plan_slug: str, period_months: int, ig_user_id: str = ""
) -> Subscription:
  now = now_tehran()
  existing = Subscription.query.filter_by(user_id=user_id, status="active").first()
  if existing and existing.expires_at > now:
    starts = existing.expires_at
  else:
    starts = now
    if existing:
      existing.status = "expired"

  expires = starts + datetime.timedelta(days=30 * period_months)
  if not ig_user_id:
    ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
    ig_user_id = ig.ig_user_id if ig else ""

  sub = Subscription(
    user_id=user_id,
    plan_slug=plan_slug,
    period_months=period_months,
    is_trial=False,
    ig_user_id=ig_user_id,
    status="active",
    starts_at=starts,
    expires_at=expires,
  )
  db.session.add(sub)
  db.session.commit()
  return sub


def validate_plan_for_user(user_id: int, plan_slug: str) -> tuple[bool, str]:
  plan = get_plan(plan_slug)
  if not plan or not plan.is_active:
    return False, "پلن نامعتبر است."
  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  if not ig:
    return False, "ابتدا پیج اینستاگرام را وصل کن."
  followers = ig.follower_count or 0
  if followers < plan.follower_min or followers > plan.follower_max:
    needed = plan_for_followers(followers)
    return False, f"پیج شما {followers:,} فالوور دارد — پلن مناسب: {needed.name if needed else plan_slug}"
  return True, ""
