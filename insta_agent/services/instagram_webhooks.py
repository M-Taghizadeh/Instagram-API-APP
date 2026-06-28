"""Subscribe Instagram professional accounts to Meta app webhooks."""

import requests

from insta_agent.config import Config

GRAPH_API = Config.GRAPH_API.rstrip("/")
SUBSCRIBED_FIELDS = "messages,comments"


def _api_message(data) -> str:
  if not isinstance(data, dict):
    return str(data)
  err = data.get("error")
  if isinstance(err, dict):
    return err.get("message") or str(err)
  return str(data)


def _post_no_redirect(url: str, *, headers: dict | None = None, params: dict | None = None, data: dict | None = None) -> requests.Response:
  """POST without redirect-to-GET (Meta returns 'method type: get/post' otherwise)."""
  r = requests.post(url, headers=headers or {}, params=params, data=data, timeout=15, allow_redirects=False)
  if r.status_code in (301, 302, 303, 307, 308):
    loc = r.headers.get("Location")
    if loc:
      r = requests.post(loc, headers=headers or {}, params=params, data=data, timeout=15, allow_redirects=False)
  return r


def _get_no_redirect(url: str, *, headers: dict | None = None, params: dict | None = None) -> requests.Response:
  r = requests.get(url, headers=headers or {}, params=params, timeout=15, allow_redirects=False)
  if r.status_code in (301, 302, 303, 307, 308):
    loc = r.headers.get("Location")
    if loc:
      r = requests.get(loc, headers=headers or {}, params=params, timeout=15, allow_redirects=False)
  return r


def _subscribe_attempt(url: str, access_token: str) -> tuple[bool, str]:
  params = {"subscribed_fields": SUBSCRIBED_FIELDS, "access_token": access_token}
  bearer = {"Authorization": f"Bearer {access_token}"}
  msg = ""

  for method, kwargs in (
    ("post-bearer", {"headers": bearer, "params": {"subscribed_fields": SUBSCRIBED_FIELDS}}),
    ("post-query", {"params": params}),
    ("get-query", {}),
  ):
    try:
      if method.startswith("post"):
        r = _post_no_redirect(url, **kwargs)
      else:
        r = _get_no_redirect(url, params=params)
      data = r.json()
      if r.status_code == 200 and data.get("success"):
        print(f"[WEBHOOK_SUB] ok via {method} {url}", flush=True)
        return True, ""
      msg = _api_message(data)
      print(f"[WEBHOOK_SUB] {method} {url} -> {msg}", flush=True)
    except Exception as e:
      msg = str(e)
      print(f"[WEBHOOK_SUB] {method} {url} error: {e}", flush=True)
  return False, msg or "subscribe failed"


def subscribe_instagram_webhooks(ig_user_id: str, access_token: str) -> tuple[bool, str]:
  if not ig_user_id or not access_token:
    return False, "شناسه پیج یا توکن خالی است"

  errors: list[str] = []
  for url in (
    f"{GRAPH_API}/me/subscribed_apps",
    f"{GRAPH_API}/{ig_user_id}/subscribed_apps",
  ):
    ok, err = _subscribe_attempt(url, access_token)
    if ok:
      print(f"[WEBHOOK_SUB] subscribed {ig_user_id} fields={SUBSCRIBED_FIELDS}", flush=True)
      return True, ""
    if err:
      errors.append(err)

  msg = errors[-1] if errors else "ثبت Webhook ناموفق بود"
  print(f"[WEBHOOK_SUB] failed {ig_user_id}: {msg}", flush=True)
  return False, msg


def get_webhook_subscription(ig_user_id: str, access_token: str) -> dict:
  """Return {subscribed: bool, fields: list[str], error: str}."""
  if not ig_user_id or not access_token:
    return {"subscribed": False, "fields": [], "error": "no token"}

  bearer = {"Authorization": f"Bearer {access_token}"}
  params = {"access_token": access_token}
  last_err = ""

  for url in (
    f"{GRAPH_API}/me/subscribed_apps",
    f"{GRAPH_API}/{ig_user_id}/subscribed_apps",
  ):
    for headers, qparams in ((bearer, None), (None, params)):
      try:
        r = _get_no_redirect(url, headers=headers or {}, params=qparams)
        data = r.json()
        if r.status_code != 200:
          last_err = (data.get("error") or {}).get("message", str(data))
          continue
        rows = data.get("data") or []
        fields: list[str] = []
        for row in rows:
          fields.extend(row.get("subscribed_fields") or [])
        fields = sorted(set(fields))
        needed = {f.strip() for f in SUBSCRIBED_FIELDS.split(",")}
        subscribed = needed.issubset(set(fields))
        return {"subscribed": subscribed, "fields": fields, "error": ""}
      except Exception as e:
        last_err = str(e)

  return {"subscribed": False, "fields": [], "error": last_err}
