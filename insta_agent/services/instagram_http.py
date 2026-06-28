"""Shared HTTP helpers for Instagram Graph API (avoid POST→GET redirects)."""

import requests

from insta_agent.config import Config

GRAPH_API = Config.GRAPH_API.rstrip("/")


def api_message(data) -> str:
  if not isinstance(data, dict):
    return str(data)
  err = data.get("error")
  if isinstance(err, dict):
    return err.get("message") or str(err)
  return str(data)


def post_no_redirect(
  url: str,
  *,
  headers: dict | None = None,
  params: dict | None = None,
  data: dict | None = None,
) -> requests.Response:
  r = requests.post(
    url, headers=headers or {}, params=params, data=data, timeout=20, allow_redirects=False
  )
  if r.status_code in (301, 302, 303, 307, 308):
    loc = r.headers.get("Location")
    if loc:
      r = requests.post(
        loc, headers=headers or {}, params=params, data=data, timeout=20, allow_redirects=False
      )
  return r


def get_no_redirect(
  url: str,
  *,
  headers: dict | None = None,
  params: dict | None = None,
) -> requests.Response:
  r = requests.get(url, headers=headers or {}, params=params, timeout=20, allow_redirects=False)
  if r.status_code in (301, 302, 303, 307, 308):
    loc = r.headers.get("Location")
    if loc:
      r = requests.get(loc, headers=headers or {}, params=params, timeout=20, allow_redirects=False)
  return r


def get_json(url: str, params: dict) -> tuple[dict, int, str]:
  r = get_no_redirect(url, params=params)
  try:
    data = r.json()
  except Exception:
    data = {}
  err = "" if r.status_code == 200 else api_message(data)
  return data if isinstance(data, dict) else {}, r.status_code, err
