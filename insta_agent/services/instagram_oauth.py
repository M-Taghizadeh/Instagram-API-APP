import requests
from urllib.parse import urlencode

from insta_agent.config import Config
from insta_agent.services.instagram_http import GRAPH_API, api_message, get_no_redirect, post_no_redirect

AUTH_URL = "https://www.instagram.com/oauth/authorize/third_party"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_LOGIN_URL = Config.INSTAGRAM_LOGIN_URL
ALLOWED_ACCOUNT_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}
LONG_LIVED_MIN_EXPIRES = 86400  # > 1 day => long-lived exchange worked


def _unwrap_payload(data) -> dict:
  if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
    first = data["data"][0]
    if isinstance(first, dict):
      return first
  return data if isinstance(data, dict) else {}


def build_authorize_url(state: str = "", force_reauth: bool | None = None) -> str:
  redirect = Config.OAUTH_REDIRECT_URI or ""
  params = {
    "client_id": Config.META_APP_ID,
    "redirect_uri": redirect,
    "response_type": "code",
    "scope": Config.OAUTH_SCOPES,
  }
  if (force_reauth if force_reauth is not None else Config.OAUTH_FORCE_REAUTH):
    params["force_reauth"] = "true"
  if state:
    params["state"] = state
  return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
  payload = {
    "client_id": Config.META_APP_ID,
    "client_secret": Config.META_APP_SECRET,
    "grant_type": "authorization_code",
    "redirect_uri": Config.OAUTH_REDIRECT_URI,
    "code": code,
  }
  r = post_no_redirect(TOKEN_URL, data=payload)
  data = _unwrap_payload(r.json())
  if r.status_code != 200:
    raise ValueError(api_message(data) or r.text)
  if not data.get("access_token"):
    raise ValueError("توکن کوتاه‌مدت از اینستاگرام دریافت نشد.")
  perms = str(data.get("permissions") or "")
  if perms and "instagram_business_basic" not in perms:
    raise ValueError(
      "اینستاگرام دسترسی View profile (instagram_business_basic) را نداد. "
      f"فقط این‌ها داده شد: {perms}. "
      "اکانت را در اپ اینستاگرام کامل Professional کن یا در Meta Dashboard به Instagram Testers اضافه کن."
    )
  return data


def exchange_long_lived_token(short_token: str) -> dict:
  """Exchange short-lived token for ~60-day token (Instagram Login API)."""
  if not short_token:
    raise ValueError("توکن کوتاه‌مدت خالی است.")

  base_params = {
    "grant_type": "ig_exchange_token",
    "client_secret": Config.META_APP_SECRET,
    "access_token": short_token,
  }
  url = f"{GRAPH_API}/access_token"
  errors: list[str] = []

  for label, fn in (
    ("GET", lambda: get_no_redirect(url, params=base_params)),
    ("POST", lambda: post_no_redirect(url, data=base_params)),
  ):
    try:
      r = fn()
      data = r.json()
      token = data.get("access_token", "")
      expires = int(data.get("expires_in") or 0)
      if r.status_code == 200 and token:
        print(f"[IG OAuth] long-lived via {label} expires_in={expires}", flush=True)
        return {"access_token": token, "expires_in": expires or 5184000}
      errors.append(f"{label}: {api_message(data) or r.text}")
    except Exception as e:
      errors.append(f"{label}: {e}")

  print(f"[IG OAuth] long-lived exchange failed: {' | '.join(errors)}", flush=True)
  return {"access_token": short_token, "expires_in": 3600, "error": " | ".join(errors)}


from insta_agent.services.instagram_profile import (
  fetch_ig_profile_fast, probe_me, debug_user_token, format_token_error, explain_meta_api_error,
)


def resolve_access_token(short_token: str) -> tuple[str, int, str]:
  """Prefer 60-day token; short-lived only if exchange fails."""
  long = exchange_long_lived_token(short_token)
  token = long.get("access_token", short_token)
  expires = int(long.get("expires_in", 0))
  exchange_err = long.get("error", "")

  if expires >= LONG_LIVED_MIN_EXPIRES:
    ok, err = probe_me(token)
    print(f"[IG OAuth] long token probe ok={ok} expires_in={expires} err={err}", flush=True)
    return token, expires, exchange_err

  ok, err = probe_me(short_token)
  print(f"[IG OAuth] short token only ok={ok} err={err}", flush=True)
  if short_token:
    return short_token, 3600, exchange_err or err

  dbg = debug_user_token(short_token)
  raise ValueError(format_token_error(dbg, err))


def get_me_optional(access_token: str, ig_user_id: str = "") -> dict:
  profile, _ = fetch_ig_profile_fast(access_token, ig_user_id)
  if profile.get("user_id") or profile.get("username"):
    return profile
  print(f"[IG OAuth] profile fetch empty for user_id={ig_user_id}", flush=True)
  return {"user_id": ig_user_id, "username": ""}


def is_professional_account(account_type: str) -> bool:
  return (account_type or "").upper() in ALLOWED_ACCOUNT_TYPES


def oauth_configured() -> bool:
  return bool(Config.META_APP_ID and Config.META_APP_SECRET and Config.OAUTH_REDIRECT_URI)


def oauth_status() -> dict:
  return {
    "ready": oauth_configured(),
    "app_id": bool(Config.META_APP_ID),
    "app_secret": bool(Config.META_APP_SECRET),
    "redirect_uri": bool(Config.OAUTH_REDIRECT_URI),
    "redirect_value": Config.OAUTH_REDIRECT_URI or "",
  }
