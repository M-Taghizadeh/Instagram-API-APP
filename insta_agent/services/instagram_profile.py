import requests

from insta_agent.config import Config
from insta_agent.utils import now_tehran

GRAPH_BASE = "https://graph.instagram.com"
GRAPH_API = Config.GRAPH_API

PROFILE_FIELDS = (
  "user_id,username,name,account_type,profile_picture_url,biography,"
  "followers_count,follows_count,media_count"
)
BASIC_FIELDS = "user_id,username,name,account_type,profile_picture_url,biography"
MIN_FIELDS = "user_id,username,account_type"


def _unwrap_payload(data) -> dict:
  if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
    first = data["data"][0]
    if isinstance(first, dict):
      return first
  return data if isinstance(data, dict) else {}


def _graph_get(url: str, params: dict) -> dict:
  if not params.get("access_token"):
    return {}
  try:
    r = requests.get(url, params=params, timeout=15, allow_redirects=False)
    if r.status_code in (301, 302, 303, 307, 308):
      loc = r.headers.get("Location")
      if loc:
        r = requests.get(loc, params=params, timeout=15, allow_redirects=False)
    data = _unwrap_payload(r.json())
    if r.status_code == 200 and data and "error" not in data:
      if not data.get("user_id") and data.get("id"):
        data["user_id"] = data["id"]
      return data
    if isinstance(data, dict) and data.get("error"):
      err = data["error"]
      msg = err.get("message", err) if isinstance(err, dict) else err
      print(f"[IG PROFILE] {url} -> {msg}", flush=True)
  except Exception as e:
    print(f"[IG PROFILE] GET {url} error: {e}", flush=True)
  return {}


def fetch_ig_profile(access_token: str, ig_user_id: str = "") -> dict:
  """Fetch Instagram professional account profile from Graph API."""
  if not access_token:
    return {}

  paths = ["/me"]
  if ig_user_id:
    paths.append(f"/{ig_user_id}")

  bases = [GRAPH_BASE, GRAPH_API.rstrip("/")]
  field_sets = [MIN_FIELDS, BASIC_FIELDS, PROFILE_FIELDS]

  for base in bases:
    for path in paths:
      for fields in field_sets:
        profile = _graph_get(f"{base}{path}", {"fields": fields, "access_token": access_token})
        if profile.get("user_id") or profile.get("username"):
          return profile
  return {}


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
