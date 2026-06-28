import os
import requests
from urllib.parse import urlencode

from insta_agent.config import Config

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
ALLOWED_ACCOUNT_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}


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
  data = r.json()
  if r.status_code != 200:
    raise ValueError(data.get("error_message") or data.get("error", {}).get("message") or r.text)
  return data


def exchange_long_lived_token(short_token: str) -> dict:
  r = requests.get(f"{Config.GRAPH_API.replace('/v25.0', '')}/access_token", params={
    "grant_type": "ig_exchange_token",
    "client_secret": Config.META_APP_SECRET,
    "access_token": short_token,
  }, timeout=15)
  data = r.json()
  if r.status_code != 200:
    raise ValueError(data.get("error", {}).get("message", r.text))
  return data


def get_me(access_token: str) -> dict:
  r = requests.get(f"{Config.GRAPH_API}/me", params={
    "fields": "user_id,username,name,account_type,profile_picture_url,followers_count",
    "access_token": access_token,
  }, timeout=15)
  data = r.json()
  if r.status_code != 200:
    raise ValueError(data.get("error", {}).get("message", r.text))
  return data


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
