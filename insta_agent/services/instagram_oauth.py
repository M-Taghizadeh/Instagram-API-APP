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
  r = requests.post(TOKEN_URL, data={
    "client_id": Config.META_APP_ID,
    "client_secret": Config.META_APP_SECRET,
    "grant_type": "authorization_code",
    "redirect_uri": Config.OAUTH_REDIRECT_URI,
    "code": code,
  }, timeout=15)
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
        r = requests.post(f"{GRAPH_BASE}/access_token", data=payload, timeout=15)
      else:
        r = requests.get(f"{GRAPH_BASE}/access_token", params=payload, timeout=15)
      data = r.json()
      if r.status_code == 200 and data.get("access_token"):
        return data
      errors.append(f"{method.upper()}: {_api_error(data, r.text)}")
    except Exception as e:
      errors.append(f"{method.upper()}: {e}")

  print(f"[IG OAuth] long-lived token fallback to short-lived: {' | '.join(errors)}", flush=True)
  return {"access_token": short_token, "expires_in": 3600}


def get_me(access_token: str) -> dict:
  if not access_token:
    raise ValueError("توکن دسترسی خالی است.")

  urls = [f"{GRAPH_BASE}/me", f"{Config.GRAPH_API}/me"]
  field_sets = [
    "user_id,username,account_type",
    "user_id,username,name,account_type,profile_picture_url,followers_count",
  ]
  last_error = ""

  for url in urls:
    for fields in field_sets:
      r = requests.get(url, params={"fields": fields, "access_token": access_token}, timeout=15)
      data = _unwrap_payload(r.json())
      if r.status_code == 200 and (data.get("user_id") or data.get("username")):
        return data
      last_error = _api_error(data, r.text)

  raise ValueError(last_error or "پروفایل اینستاگرام دریافت نشد.")


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
