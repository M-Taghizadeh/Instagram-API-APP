import requests

from insta_agent.config import Config
from insta_agent.services.instagram_http import GRAPH_API, get_no_redirect, post_no_redirect
from insta_agent.utils import now_tehran

GRAPH_BASE = "https://graph.instagram.com"
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
  app_tok = _app_access_token()
  last_error = ""
  for base in (FB_GRAPH, GRAPH_BASE):
    try:
      r = requests.get(
        f"{base}/debug_token",
        params={"input_token": access_token, "access_token": app_tok},
        timeout=15,
      )
      raw = r.json()
      if isinstance(raw, dict) and raw.get("error"):
        err = raw["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        last_error = msg
        continue
      result = _unwrap_payload(raw)
      if result:
        result["configured_app_id"] = Config.META_APP_ID
        if result.get("app_id"):
          result["app_id_match"] = str(result["app_id"]) == str(Config.META_APP_ID)
        return result
    except Exception as e:
      last_error = str(e)
      print(f"[IG PROFILE] debug_token ({base}) error: {e}", flush=True)
  return {
    "is_valid": None,
    "debug_unreliable": True,
    "debug_error": last_error,
    "configured_app_id": Config.META_APP_ID,
  }


def probe_me(access_token: str, ig_user_id: str = "") -> tuple[bool, str]:
  if not access_token:
    return False, "no token"
  min_fields = {"fields": "user_id,username"}
  version = (Config.GRAPH_API or "").rstrip("/").split("/")[-1]
  versions = [v for v in (version, "v25.0", "v22.0", "v21.0", "v20.0") if v.startswith("v")]
  seen: set[str] = set()
  me_urls: list[str] = []
  for v in versions:
    if v not in seen:
      seen.add(v)
      me_urls.append(f"{GRAPH_BASE}/{v}/me")
  me_urls.append(f"{GRAPH_BASE}/me")
  if ig_user_id:
    for v in versions:
      me_urls.append(f"{GRAPH_BASE}/{v}/{ig_user_id}")
      me_urls.append(f"{GRAPH_BASE}/{ig_user_id}")
  last_err = ""
  for url in me_urls:
    for headers, params in (
      ({}, {**min_fields, "access_token": access_token}),
      ({"Authorization": f"Bearer {access_token}"}, min_fields),
    ):
      try:
        r = get_no_redirect(url, headers=headers, params=params)
        raw = r.json()
        if r.status_code == 200 and "error" not in raw:
          data = _normalize_profile(_unwrap_payload(raw))
          if data.get("user_id") or data.get("username"):
            return True, ""
        err = raw.get("error", {}) if isinstance(raw, dict) else {}
        last_err = err.get("message", r.text) if isinstance(err, dict) else r.text
      except Exception as e:
        last_err = str(e)
  return False, last_err


def token_health_report(access_token: str) -> dict:
  dbg = debug_user_token(access_token)
  me_ok, me_err = probe_me(access_token)
  return {
    "token_length": len(access_token or ""),
    "configured_app_id": Config.META_APP_ID,
    "debug": dbg,
    "me_works": me_ok,
    "me_error": me_err,
    "app_id_match": dbg.get("app_id_match"),
    "token_app_id": dbg.get("app_id"),
    "scopes": dbg.get("scopes"),
    "is_valid": dbg.get("is_valid"),
  }


def format_token_error(debug: dict, me_err: str = "") -> str:
  if debug.get("app_id_match") is False:
    return (
      f"META_APP_ID در Render ({debug.get('configured_app_id')}) "
      f"با اپ صادرکننده توکن ({debug.get('app_id')}) یکی نیست. "
      "در Render باید Instagram App ID و Instagram App Secret از "
      "Meta Dashboard → Instagram → API setup with Instagram login باشد "
      "(نه App ID بالای صفحه اپ)."
    )
  if debug.get("debug_unreliable") and me_err:
    if "expired" in me_err.lower():
      return "توکن منقضی شده — دوباره «اتصال پیج اینستاگرام» را بزن."
    if "429" in me_err or "rate" in me_err.lower():
      return "محدودیت موقت اینستاگرام — چند دقیقه بعد دوباره تلاش کن."
    if "method type" in me_err.lower():
      return explain_meta_api_error(me_err)
    return f"Instagram API: {me_err}"
  if debug.get("debug_error") and not debug.get("debug_unreliable"):
    return f"خطا در بررسی توکن: {debug['debug_error']}"
  if debug.get("is_valid") is False:
    return "توکن نامعتبر یا منقضی — قطع اتصال و دوباره Allow بزن."
  if me_err:
    if "method type" in me_err.lower():
      return (
        f"Instagram Graph API درخواست را رد کرد: {me_err}. "
        "احتمالاً App ID/Secret اشتباه است یا دسترسی‌های instagram_business_* "
        "در App Review هنوز Advanced نشده‌اند."
      )
    return me_err
  return "توکن به Instagram Graph API دسترسی ندارد."


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
        r = get_no_redirect(url, headers=headers, params=params)
      else:
        r = post_no_redirect(
          url,
          headers=headers,
          data={"fields": fields, "access_token": access_token},
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
  return format_token_error(token_debug, api_error)


def explain_meta_api_error(msg: str) -> str:
  low = (msg or "").lower()
  if "method type" in low:
    return (
      "Instagram API: " + (msg or "Unsupported request - method type: get") + ". "
      "معمولاً یعنی دسترسی instagram_business_basic هنوز Advanced نیست، "
      "Business Verification کامل نشده، یا اپ Live نیست. "
      "در Meta Dashboard: App Review → Advanced Access + Settings → Business verification."
    )
  if "expired" in low:
    return "توکن منقضی شده — دوباره اتصال پیج را بزن."
  return msg or "خطای ناشناخته از Instagram API"


def fetch_ig_profile_fast(access_token: str, ig_user_id: str = "") -> tuple[dict, str]:
  """GET /me with Bearer or query token."""
  if not access_token:
    return {}, "توکن خالی است"

  urls = [f"{GRAPH_API}/me"]
  if ig_user_id:
    urls.append(f"{GRAPH_API}/{ig_user_id}")

  last_err = ""
  for url in urls:
    for fields in (PROFILE_FIELDS, MIN_FIELDS):
      for mode, headers, extra in (
        ("bearer", {"Authorization": f"Bearer {access_token}"}, {"fields": fields}),
        ("query", {}, {"fields": fields, "access_token": access_token}),
      ):
        try:
          r = get_no_redirect(url, headers=headers, params=extra)
          raw = r.json()
          if r.status_code == 200 and isinstance(raw, dict) and "error" not in raw:
            data = _normalize_profile(_unwrap_payload(raw))
            if data.get("username") or data.get("user_id"):
              return data, ""
          err = raw.get("error", {}) if isinstance(raw, dict) else {}
          last_err = err.get("message", r.text) if isinstance(err, dict) else r.text
        except Exception as e:
          last_err = str(e)
  return {}, last_err


def fetch_ig_profile(access_token: str, ig_user_id: str = "") -> dict:
  profile, _ = fetch_ig_profile_fast(access_token, ig_user_id)
  if profile:
    return profile
  profile, _ = fetch_ig_profile_with_debug(access_token, ig_user_id)
  return profile


def fetch_ig_profile_with_debug(access_token: str, ig_user_id: str = "") -> tuple[dict, str]:
  if not access_token:
    return {}, "توکن خالی است"

  token_debug = debug_user_token(access_token)
  urls = [f"{GRAPH_API}/me"]
  if ig_user_id:
    urls.append(f"{GRAPH_API}/{ig_user_id}")

  err = ""
  for url in urls:
    profile, err = _graph_read(url, access_token, MIN_FIELDS)
    if profile:
      full, _ = _graph_read(url, access_token, PROFILE_FIELDS)
      return full or profile, ""

  refreshed = refresh_ig_access_token(access_token)
  new_token = refreshed.get("access_token", "")
  if new_token and new_token != access_token:
    for url in urls:
      profile, err = _graph_read(url, new_token, MIN_FIELDS)
      if profile:
        full, _ = _graph_read(url, new_token, PROFILE_FIELDS)
        merged = full or profile
        merged["_refreshed_access_token"] = new_token
        merged["_expires_in"] = refreshed.get("expires_in")
        return merged, ""

  return {}, format_token_error(token_debug, err)


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
