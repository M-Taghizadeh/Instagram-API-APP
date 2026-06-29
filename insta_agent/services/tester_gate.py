"""Beta-phase gate: Instagram Tester workflow before OAuth (disable via BETA_TESTER_GATE=false)."""

from insta_agent.config import Config
from insta_agent.models import IgAccount

TESTER_STATUSES = ("none", "pending", "invited", "ready", "connected")
INSTAGRAM_INVITE_URL = "https://www.instagram.com/accounts/manage_access/"


def beta_gate_enabled() -> bool:
  from insta_agent.services.app_settings_service import beta_tester_gate_enabled
  return beta_tester_gate_enabled()


def needs_beta_onboarding(user) -> bool:
  """True when user must complete beta steps before OAuth."""
  if not beta_gate_enabled():
    return False
  status = (user.tester_status or "none").lower()
  return status in ("none", "pending")


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
  return False, "اول یوزرنیم پیج اینستاگرامت را ثبت کن تا فعال‌سازی انجام شود."


def onboarding_context(user) -> dict:
  """Template context — phase: username | activate | connect."""
  gate_on = beta_gate_enabled()
  status = (user.tester_status or "none").lower()
  ig_user = user.ig_username_requested or ""

  if not gate_on:
    phase = "connect"
  elif status == "none":
    phase = "username"
  elif status == "pending":
    phase = "activate"
  else:
    phase = "connect"

  return {
    "beta_gate": gate_on,
    "phase": phase,
    "tester_status": status,
    "ig_username_requested": ig_user,
    "instagram_invite_url": INSTAGRAM_INVITE_URL,
    "can_connect": can_start_oauth(user)[0],
    "is_admin_preview": bool(user.is_admin and gate_on),
    "beta_timeline": _beta_timeline(status) if gate_on else [],
  }


def _beta_timeline(status: str) -> list:
  steps = [
    ("submitted", "ثبت درخواست"),
    ("review", "تایید سامانه"),
    ("connect", "اتصال پیج"),
  ]
  mapping = {"none": 0, "pending": 1, "invited": 2, "ready": 2, "connected": 3}
  cur = mapping.get((status or "none").lower(), 0)
  out = []
  for i, (key, label) in enumerate(steps):
    if cur >= 3:
      out.append({"key": key, "label": label, "done": True, "active": False})
    elif i < cur:
      out.append({"key": key, "label": label, "done": True, "active": False})
    elif i == cur:
      out.append({"key": key, "label": label, "done": False, "active": True})
    else:
      out.append({"key": key, "label": label, "done": False, "active": False})
  return out


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
  """After disconnect — leave admin ready list and require fresh beta onboarding."""
  if not user or not beta_gate_enabled() or user.is_admin:
    return
  status = (user.tester_status or "none").lower()
  if status not in ("ready", "connected"):
    return
  user.tester_status = "none"
  user.ig_username_requested = ""
  user.tester_requested_at = None
  user.tester_ready_at = None
