import requests

from insta_agent.config import Config
from insta_agent.utils import now_tehran

GRAPH_BASE = "https://graph.instagram.com"
GRAPH_API = Config.GRAPH_API.rstrip("/")
FB_GRAPH = "https://graph.facebook.com/v25.0"

PROFILE_FIELDS = (
  "id,user_id,username,name,account_type,profile_picture_url,biography,"
  "followers_count,follows_count,media_count"
)
MIN_FIELDS = "id,user_id,username"


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


def _app_access_token() -> str:
  return f"{Config.META_APP_ID}|{Config.META_APP_SECRET}"


def debug_user_token(access_token: str) -> dict:
  if not access_token or not Config.META_APP_ID or not Config.META_APP_SECRET:
    return {}
  try:
    r = requests.get(
      f"{GRAPH_BASE}/debug_token",
      params={"input_token": access_token, "access_token": _app_access_token()},
      timeout=15,
    )
    data = r.json()
    return _unwrap_payload(data) if isinstance(data, dict) else {}
  except Exception as e:
    print(f"[IG PROFILE] debug_token error: {e}", flush=True)
    return {}


def refresh_ig_access_token(access_token: str) -> dict:
  if not access_token:
    return {}
  try:
    r = requests.get(
      f"{GRAPH_BASE}/refresh_access_token",
      params={"grant_type": "ig_refresh_token", "access_token": access_token},
      timeout=15,
    )
    data = r.json()
    if r.status_code == 200 and data.get("access_token"):
      return data
    err = data.get("error", {})
    msg = err.get("message", r.text) if isinstance(err, dict) else r.text
    print(f"[IG PROFILE] refresh_token -> {msg}", flush=True)
  except Exception as e:
    print(f"[IG PROFILE] refresh_token error: {e}", flush=True)
  return {}


def _graph_read(url: str, access_token: str, fields: str) -> tuple[dict, str]:
  if not access_token:
    return {}, "no token"

  attempts = (
    ("bearer-get", "GET", {"Authorization": f"Bearer {access_token}"}, {"fields": fields}),
    ("query-get", "GET", {}, {"fields": fields, "access_token": access_token}),
    ("form-post", "POST", {}, None),
  )
  last_error = ""
  for mode, method, headers, params in attempts:
    try:
      if method == "GET":
        r = requests.get(url, headers=headers, params=params, timeout=15)
      else:
        r = requests.post(
          url,
          headers=headers,
          data={"fields": fields, "access_token": access_token},
          timeout=15,
        )
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
      print(f"[IG PROFILE] {url} ({mode}) error: {e}", flush=True)
  return {}, last_error


def explain_profile_failure(api_error: str, token_debug: dict) -> str:
  if token_debug and token_debug.get("is_valid") is False:
    return "توکن منقضی یا نامعتبر است — یک‌بار قطع اتصال و دوباره وصل کن."
  scopes = token_debug.get("scopes") or []
  if scopes and "instagram_business_basic" not in scopes:
    return "دسترسی instagram_business_basic داده نشده — در Allow همه دسترسی‌ها را بپذیر."

  if "method type: get" in (api_error or "").lower():
    return (
      "متا endpoint پروفایل (/me) را رد می‌کند. در Meta Developer → App Review → Permissions "
      "برای instagram_business_basic حالت Advanced Access بگیر. Live بودن اپ کافی نیست."
    )
  return api_error or "پروفایل از API دریافت نشد."


def fetch_ig_profile(access_token: str, ig_user_id: str = "") -> dict:
  profile, _ = fetch_ig_profile_with_debug(access_token, ig_user_id)
  return profile


def fetch_ig_profile_with_debug(access_token: str, ig_user_id: str = "") -> tuple[dict, str]:
  if not access_token:
    return {}, "توکن خالی است"

  token_debug = debug_user_token(access_token)
  urls = [f"{GRAPH_API}/me", f"{GRAPH_BASE}/me", f"{FB_GRAPH}/me"]
  if ig_user_id:
    urls.extend([f"{GRAPH_API}/{ig_user_id}", f"{GRAPH_BASE}/{ig_user_id}"])

  last_error = ""
  for url in urls:
    profile, err = _graph_read(url, access_token, MIN_FIELDS)
    if profile:
      full, err2 = _graph_read(url, access_token, PROFILE_FIELDS)
      return full or profile, ""
    last_error = err or last_error

  refreshed = refresh_ig_access_token(access_token)
  new_token = refreshed.get("access_token", "")
  if new_token and new_token != access_token:
    for url in urls[:2]:
      profile, err = _graph_read(url, new_token, MIN_FIELDS)
      if profile:
        full, _ = _graph_read(url, new_token, PROFILE_FIELDS)
        merged = full or profile
        merged["_refreshed_access_token"] = new_token
        merged["_expires_in"] = refreshed.get("expires_in")
        return merged, ""
      last_error = err or last_error

  return {}, explain_profile_failure(last_error, token_debug)


def apply_profile_to_account(account, profile: dict) -> bool:
  if not profile:
    return False

  changed = False
  if profile.get("_refreshed_access_token"):
    account.access_token = profile["_refreshed_access_token"]
    changed = True

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
  profile, _ = fetch_ig_profile_with_debug(token, account.ig_user_id)
  apply_profile_to_account(account, profile)
  return profile
