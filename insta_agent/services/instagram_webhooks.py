"""Subscribe Instagram professional accounts to Meta app webhooks."""

from urllib.parse import urlencode

import requests

from insta_agent.services.instagram_http import GRAPH_API, api_message, get_no_redirect
from insta_agent.services.instagram_profile import explain_meta_api_error

SUBSCRIBED_FIELDS = "messages,comments"


def subscribe_instagram_webhooks(ig_user_id: str, access_token: str) -> tuple[bool, str]:
  if not ig_user_id or not access_token:
    return False, "شناسه پیج یا توکن خالی است"

  query = urlencode({"subscribed_fields": SUBSCRIBED_FIELDS, "access_token": access_token})
  errors: list[str] = []

  for path in (f"{GRAPH_API}/{ig_user_id}/subscribed_apps", f"{GRAPH_API}/me/subscribed_apps"):
    url = f"{path}?{query}"
    try:
      # Meta docs: curl -i -X POST "url?subscribed_fields=...&access_token=..."
      r = requests.post(url, timeout=20, allow_redirects=False)
      data = r.json() if r.content else {}
      if r.status_code == 200 and data.get("success"):
        print(f"[WEBHOOK_SUB] ok POST {path}", flush=True)
        return True, ""
      msg = api_message(data) or r.text
      errors.append(msg)
      print(f"[WEBHOOK_SUB] POST {path} -> {msg}", flush=True)
    except Exception as e:
      errors.append(str(e))
      print(f"[WEBHOOK_SUB] POST {path} error: {e}", flush=True)

  raw = errors[-1] if errors else "ثبت Webhook ناموفق بود"
  return False, explain_meta_api_error(raw)


def get_webhook_subscription(ig_user_id: str, access_token: str) -> dict:
  if not ig_user_id or not access_token:
    return {"subscribed": False, "fields": [], "error": "no token"}

  params = {"access_token": access_token}
  bearer = {"Authorization": f"Bearer {access_token}"}
  last_err = ""
  needed = {f.strip() for f in SUBSCRIBED_FIELDS.split(",")}

  for path in (f"{GRAPH_API}/me/subscribed_apps", f"{GRAPH_API}/{ig_user_id}/subscribed_apps"):
    for headers, qparams in ((bearer, None), (None, params)):
      try:
        r = get_no_redirect(path, headers=headers or {}, params=qparams)
        data = r.json()
        if r.status_code != 200:
          last_err = (data.get("error") or {}).get("message", str(data))
          continue
        rows = data.get("data") or []
        fields: list[str] = []
        for row in rows:
          fields.extend(row.get("subscribed_fields") or [])
        fields = sorted(set(fields))
        return {"subscribed": needed.issubset(set(fields)), "fields": fields, "error": ""}
      except Exception as e:
        last_err = str(e)

  return {"subscribed": False, "fields": [], "error": last_err}
