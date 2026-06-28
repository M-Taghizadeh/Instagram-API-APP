import requests

from insta_agent.config import Config
from insta_agent.utils import now_tehran

GRAPH_BASE = "https://graph.instagram.com"
GRAPH_API = Config.GRAPH_API.rstrip("/")

PROFILE_FIELDS = (
  "id,user_id,username,name,account_type,profile_picture_url,biography,"
  "followers_count,follows_count,media_count"
)
BASIC_FIELDS = "id,user_id,username,name,account_type,profile_picture_url,biography"
MIN_FIELDS = "id,user_id,username,account_type"


def _unwrap_payload(data) -> dict:
  if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
    first = data["data"][0]
    if isinstance(first, dict):
      return first
  return data if isinstance(data, dict) else {}


def _normalize_profile(data: dict) -> dict:
  if not data:
    return {}
  if not data.get("user_id") and data.get("id"):
    data["user_id"] = str(data["id"])
  if data.get("user_id"):
    data["user_id"] = str(data["user_id"])
  return data


def _graph_get(url: str, access_token: str, fields: str) -> tuple[dict, str]:
  """Instagram Login tokens work reliably with Bearer auth (see instagram_api.py)."""
  if not access_token:
    return {}, "no token"

  last_error = ""
  attempts = (
    ("bearer", {"Authorization": f"Bearer {access_token}"}, {"fields": fields}),
    ("query", {}, {"fields": fields, "access_token": access_token}),
  )
  for mode, headers, params in attempts:
    try:
      r = requests.get(url, headers=headers, params=params, timeout=15)
      raw = r.json()
      data = _normalize_profile(_unwrap_payload(raw))
      if r.status_code == 200 and data and "error" not in raw:
        if data.get("user_id") or data.get("username"):
          return data, ""
      err = raw.get("error", {}) if isinstance(raw, dict) else {}
      msg = err.get("message", r.text) if isinstance(err, dict) else str(raw)
      last_error = f"{mode}: {msg}"
      print(f"[IG PROFILE] {url} ({mode}) -> {msg}", flush=True)
    except Exception as e:
      last_error = f"{mode}: {e}"
      print(f"[IG PROFILE] GET {url} ({mode}) error: {e}", flush=True)
  return {}, last_error


def fetch_ig_profile(access_token: str, ig_user_id: str = "") -> dict:
  """Fetch Instagram professional account profile from Graph API."""
  profile, _ = fetch_ig_profile_with_debug(access_token, ig_user_id)
  return profile


def fetch_ig_profile_with_debug(access_token: str, ig_user_id: str = "") -> tuple[dict, str]:
  if not access_token:
    return {}, "توکن خالی است"

  paths = ["/me"]
  if ig_user_id:
    paths.append(f"/{ig_user_id}")

  bases = [GRAPH_API, GRAPH_BASE]
  field_sets = [MIN_FIELDS, BASIC_FIELDS, PROFILE_FIELDS]
  last_error = "هیچ پاسخی از API دریافت نشد"

  for base in bases:
    for path in paths:
      for fields in field_sets:
        profile, err = _graph_get(f"{base}{path}", access_token, fields)
        if profile:
          return profile, ""
        if err:
          last_error = err
  return {}, last_error


def apply_profile_to_account(account, profile: dict) -> bool:
  """Write profile fields onto IgAccount. Returns True if anything changed."""
  if not profile:
    return False

  changed = False
  mapping = {
    "username": profile.get("username") or "",
    "name": profile.get("name") or "",
    "account_type": profile.get("account_type") or "",
    "profile_picture": profile.get("profile_picture_url") or "",
    "biography": (profile.get("biography") or "")[:500],
  }
  for attr, value in mapping.items():
    if value and getattr(account, attr, None) != value:
      setattr(account, attr, value)
      changed = True

  for attr, key in (
    ("follower_count", "followers_count"),
    ("follows_count", "follows_count"),
    ("media_count", "media_count"),
  ):
    if key not in profile:
      continue
    try:
      val = int(profile.get(key) or 0)
    except (TypeError, ValueError):
      continue
    if getattr(account, attr, None) != val:
      setattr(account, attr, val)
      changed = True

  ig_id = str(profile.get("user_id") or profile.get("id") or "")
  if ig_id and account.ig_user_id != ig_id:
    account.ig_user_id = ig_id
    changed = True

  account.profile_synced_at = now_tehran()
  return changed


def sync_ig_account_profile(account, access_token: str = "") -> dict:
  token = access_token or account.access_token or ""
  profile = fetch_ig_profile(token, account.ig_user_id)
  apply_profile_to_account(account, profile)
  return profile
