import requests

from insta_agent.config import Config
from insta_agent.utils import now_tehran

GRAPH_API = Config.GRAPH_API

PROFILE_FIELDS = (
  "user_id,username,name,account_type,profile_picture_url,biography,"
  "followers_count,follows_count,media_count"
)
BASIC_FIELDS = "user_id,username,name,account_type,profile_picture_url,biography"


def _api_get(path: str, access_token: str, fields: str) -> dict:
  if not access_token:
    return {}
  try:
    r = requests.get(
      f"{GRAPH_API}{path}",
      params={"fields": fields, "access_token": access_token},
      timeout=15,
    )
    data = r.json()
    if r.status_code == 200 and "error" not in data:
      return data
  except Exception as e:
    print(f"[IG PROFILE] GET {path} error: {e}", flush=True)
  return {}


def fetch_ig_profile(access_token: str, ig_user_id: str = "") -> dict:
  """Fetch Instagram professional account profile from Graph API."""
  profile = _api_get("/me", access_token, PROFILE_FIELDS)
  if not profile:
    profile = _api_get("/me", access_token, BASIC_FIELDS)
  if not profile and ig_user_id:
    profile = _api_get(f"/{ig_user_id}", access_token, PROFILE_FIELDS)
  if not profile and ig_user_id:
    profile = _api_get(f"/{ig_user_id}", access_token, BASIC_FIELDS)
  return profile or {}


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

  ig_id = str(profile.get("user_id") or "")
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
