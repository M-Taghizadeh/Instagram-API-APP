"""Beta-phase gate: Instagram Tester workflow before OAuth (disable via BETA_TESTER_GATE=false)."""

from insta_agent.config import Config
from insta_agent.models import IgAccount

TESTER_STATUSES = ("none", "pending", "invited", "ready", "connected")
INSTAGRAM_INVITE_URL = "https://www.instagram.com/accounts/manage_access/"


def beta_gate_enabled() -> bool:
  from insta_agent.services.app_settings_service import beta_tester_gate_enabled
  return beta_tester_gate_enabled()


def normalize_ig_username(raw: str) -> str:
  u = (raw or "").strip().lstrip("@").lower()
  u = u.split("/")[-1].split("?")[0]
  return u


def user_has_connection(user) -> bool:
  if not user:
    return False
  try:
    if user.primary_ig_account:
      return True
  except Exception:
    pass
  return IgAccount.query.filter_by(user_id=user.id).count() > 0


def can_start_oauth(user) -> tuple[bool, str]:
  if not beta_gate_enabled():
    return True, ""
  if not user:
    return False, "ابتدا وارد حساب کاربری شو."
  if user.is_admin:
    return True, ""
  if user_has_connection(user):
    return True, ""

  status = (user.tester_status or "none").lower()
  if status in ("ready", "connected"):
    return True, ""

  if status == "pending":
    return False, (
      "درخواستت ثبت شده — تیم محتوام داره پیجت رو فعال می‌کنه. "
      "معمولاً تا چند ساعت آماده می‌شه."
    )
  if status == "invited":
    return False, (
      "دعوت اینستاگرام ارسال شده — اول در اینستاگرام دعوت را Accept کن، "
      "بعد «قبول کردم» را بزن."
    )
  return False, "اول یوزرنیم پیج اینستاگرامت را ثبت کن تا فعال‌سازی انجام شود."


def onboarding_context(user) -> dict:
  """Template context for onboarding wizard."""
  gate = beta_gate_enabled() and not user.is_admin
  status = (user.tester_status or "none").lower()
  ig_user = user.ig_username_requested or ""

  if not gate:
    step = "connect"
  elif status == "none":
    step = "request"
  elif status == "pending":
    step = "waiting"
  elif status == "invited":
    step = "accept"
  elif status in ("ready", "connected"):
    step = "connect"
  else:
    step = "request"

  return {
    "beta_gate": gate,
    "tester_step": step,
    "tester_status": status,
    "ig_username_requested": ig_user,
    "instagram_invite_url": INSTAGRAM_INVITE_URL,
    "can_connect": can_start_oauth(user)[0],
    "tester_slots_max": Config.BETA_TESTER_SLOTS,
    "tester_slots_used": count_tester_slots_used(),
  }


def count_tester_slots_used() -> int:
  from insta_agent.models import User

  if not beta_gate_enabled():
    return 0
  return User.query.filter(
    User.is_admin == False,
    User.tester_status.in_(("pending", "invited", "ready", "connected")),
  ).count()


def mark_connected(user):
  if not user:
    return
  user.tester_status = "connected"


def reset_for_reconnect(user):
  """After disconnect — user remains a Meta tester; allow OAuth again."""
  if not user or not beta_gate_enabled():
    return
  if (user.tester_status or "") == "connected":
    user.tester_status = "ready"
