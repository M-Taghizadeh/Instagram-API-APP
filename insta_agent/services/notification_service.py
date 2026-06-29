from insta_agent.config import Config
from insta_agent.extensions import db
from insta_agent.models import User, Notification
from insta_agent.utils import now_tehran


def meta_roles_url() -> str:
  app_id = (Config.META_APP_ID or "").strip()
  if app_id:
    return f"https://developers.facebook.com/apps/{app_id}/roles/roles/"
  return "https://developers.facebook.com/apps/"


def _admin_users() -> list:
  return User.query.filter_by(is_admin=True).all()


def create_notification(
  user_id: int,
  *,
  kind: str,
  title: str,
  body: str = "",
  action_url: str = "",
  action_label: str = "",
  ig_username: str = "",
) -> Notification:
  n = Notification(
    user_id=user_id,
    kind=kind,
    title=title,
    body=body,
    action_url=action_url or "",
    action_label=action_label or "",
    ig_username=(ig_username or "").lstrip("@").lower(),
  )
  db.session.add(n)
  return n


def notify_admins_new_tester_request(requester: User, ig_username: str):
  ig = (ig_username or "").lstrip("@").lower()
  uname = requester.username
  meta_url = meta_roles_url()
  body = (
    f"کاربر {uname} درخواست اتصال @{ig} را ثبت کرد. "
    f"در Meta → Instagram Tester اضافه کن، بعد در صف فعال‌سازی «آماده اتصال» بزن."
  )
  for admin in _admin_users():
    create_notification(
      admin.id,
      kind="admin_tester_request",
      title=f"درخواست جدید: @{ig}",
      body=body,
      action_url=meta_url,
      action_label="اتصال به متا",
      ig_username=ig,
    )
  db.session.commit()


def notify_user_tester_pending(user_id: int, ig_username: str):
  ig = (ig_username or "").lstrip("@").lower()
  create_notification(
    user_id,
    kind="user_pending",
    title="در انتظار تایید سامانه",
    body=f"پیج @{ig} ثبت شد. تیم محتوام در حال فعال‌سازی است — معمولاً کمتر از چند ساعت.",
    action_url="",
    action_label="",
    ig_username=ig,
  )
  db.session.commit()


def notify_user_tester_invited(user_id: int, ig_username: str):
  ig = (ig_username or "").lstrip("@").lower()
  create_notification(
    user_id,
    kind="user_invited",
    title="دعوت اینستاگرام آماده است",
    body=f"پیج @{ig} در Meta ثبت شد. دعوت را در اینستاگرام Accept کن؛ بعد از تأیید نهایی سامانه اتصال فعال می‌شود.",
    action_url="https://www.instagram.com/accounts/manage_access/",
    action_label="تنظیمات اینستاگرام",
    ig_username=ig,
  )
  db.session.commit()


def notify_user_tester_ready(user_id: int, ig_username: str):
  ig = (ig_username or "").lstrip("@").lower()
  create_notification(
    user_id,
    kind="user_ready",
    title="پیجت آماده اتصال است",
    body=(
      f"دعوت @{ig} در اینستاگرام ارسال شده. "
      f"اول در تنظیمات اینستاگرام Accept کن، بعد «اتصال پیج» را بزن."
    ),
    action_url="",
    action_label="",
    ig_username=ig,
  )
  db.session.commit()


def unread_count(user_id: int) -> int:
  return Notification.query.filter_by(user_id=user_id, read_at=None).count()


def list_notifications(user_id: int, limit: int = 40) -> list:
  return (
    Notification.query.filter_by(user_id=user_id)
    .order_by(Notification.created_at.desc())
    .limit(limit)
    .all()
  )


def mark_read(notification_id: int, user_id: int) -> bool:
  n = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
  if not n or n.read_at:
    return False
  n.read_at = now_tehran()
  db.session.commit()
  return True


def mark_all_read(user_id: int) -> int:
  rows = Notification.query.filter_by(user_id=user_id, read_at=None).all()
  now = now_tehran()
  for n in rows:
    n.read_at = now
  db.session.commit()
  return len(rows)


def delete_notification(notification_id: int, user_id: int) -> bool:
  n = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
  if not n:
    return False
  db.session.delete(n)
  db.session.commit()
  return True


def delete_all_notifications(user_id: int) -> int:
  count = Notification.query.filter_by(user_id=user_id).delete()
  db.session.commit()
  return count
