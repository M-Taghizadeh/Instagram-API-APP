import os
import requests
from urllib.parse import urlencode

from insta_agent.config import Config

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_BASE = "https://graph.instagram.com"
ALLOWED_ACCOUNT_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}


def _unwrap_payload(data) -> dict:
  if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
    first = data["data"][0]
    if isinstance(first, dict):
      return first
  return data if isinstance(data, dict) else {}


def _api_error(data, fallback: str = "") -> str:
  if not isinstance(data, dict):
    return fallback or "خطای ناشناخته"
  err = data.get("error")
  if isinstance(err, dict):
    return err.get("message") or fallback or str(err)
  return data.get("error_message") or fallback or str(data)


def _post_form(url: str, payload: dict) -> requests.Response:
  """POST form without redirect-to-GET (causes Meta 'method type: get' errors)."""
  r = requests.post(url, data=payload, timeout=15, allow_redirects=False)
  if r.status_code in (301, 302, 303, 307, 308):
    loc = r.headers.get("Location")
    if loc:
      r = requests.post(loc, data=payload, timeout=15, allow_redirects=False)
  return r


def _get_json(url: str, params: dict) -> requests.Response:
  r = requests.get(url, params=params, timeout=15, allow_redirects=False)
  if r.status_code in (301, 302, 303, 307, 308):
    loc = r.headers.get("Location")
    if loc:
      r = requests.get(loc, params=params, timeout=15, allow_redirects=False)
  return r


def build_authorize_url(state: str = "") -> str:
  redirect = Config.OAUTH_REDIRECT_URI or ""
  params = {
    "client_id": Config.META_APP_ID,
    "redirect_uri": redirect,
    "response_type": "code",
    "scope": Config.OAUTH_SCOPES,
  }
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
  r = _post_form(TOKEN_URL, payload)
  data = _unwrap_payload(r.json())
  if r.status_code != 200:
    raise ValueError(_api_error(data, r.text))
  if not data.get("access_token"):
    raise ValueError("توکن کوتاه‌مدت از اینستاگرام دریافت نشد.")
  return data


def exchange_long_lived_token(short_token: str) -> dict:
  if not short_token:
    raise ValueError("توکن کوتاه‌مدت خالی است.")

  payload = {
    "grant_type": "ig_exchange_token",
    "client_secret": Config.META_APP_SECRET,
    "access_token": short_token,
  }
  errors: list[str] = []

  for method in ("post", "get"):
    try:
      if method == "post":
        r = _post_form(f"{GRAPH_BASE}/access_token", payload)
      else:
        r = _get_json(f"{GRAPH_BASE}/access_token", payload)
      data = r.json()
      if r.status_code == 200 and data.get("access_token"):
        return data
      errors.append(f"{method.upper()}: {_api_error(data, r.text)}")
    except Exception as e:
      errors.append(f"{method.upper()}: {e}")

  print(f"[IG OAuth] long-lived token fallback to short-lived: {' | '.join(errors)}", flush=True)
  return {"access_token": short_token, "expires_in": 3600}


from insta_agent.services.instagram_profile import fetch_ig_profile, probe_me, debug_user_token, format_token_error


def resolve_access_token(short_token: str) -> tuple[str, int]:
  """Use short or long-lived token — whichever actually works on Graph API."""
  short_ok, short_err = probe_me(short_token)
  print(f"[IG OAuth] short token probe: ok={short_ok} err={short_err}", flush=True)

  long = exchange_long_lived_token(short_token)
  long_token = long.get("access_token", short_token)
  if long_token != short_token:
    long_ok, long_err = probe_me(long_token)
    print(f"[IG OAuth] long token probe: ok={long_ok} err={long_err}", flush=True)
    if long_ok:
      return long_token, int(long.get("expires_in", 5184000))

  if short_ok:
    return short_token, 3600

  dbg = debug_user_token(short_token)
  print(f"[IG OAuth] token debug: {dbg}", flush=True)
  raise ValueError(format_token_error(dbg, short_err))


def get_me_optional(access_token: str, ig_user_id: str = "") -> dict:
  profile = fetch_ig_profile(access_token, ig_user_id)
  if profile.get("user_id") or profile.get("username"):
    return profile
  print(f"[IG OAuth] profile fetch empty for user_id={ig_user_id}", flush=True)
  return {"user_id": ig_user_id, "username": ""}


def is_professional_account(account_type: str) -> bool:
  return (account_type or "").upper() in ALLOWED_ACCOUNT_TYPES


def oauth_configured() -> bool:
  return bool(Config.META_APP_ID and Config.META_APP_SECRET and Config.OAUTH_REDIRECT_URI)


def oauth_status() -> dict:
  """وضعیت تنظیمات OAuth — برای نمایش در onboarding"""
  return {
    "ready": oauth_configured(),
    "app_id": bool(Config.META_APP_ID),
    "app_secret": bool(Config.META_APP_SECRET),
    "redirect_uri": bool(Config.OAUTH_REDIRECT_URI),
    "redirect_value": Config.OAUTH_REDIRECT_URI or "",
  }
