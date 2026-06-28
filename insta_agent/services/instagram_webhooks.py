"""Subscribe Instagram professional accounts to Meta app webhooks."""

import requests

from insta_agent.config import Config

GRAPH_API = Config.GRAPH_API.rstrip("/")
SUBSCRIBED_FIELDS = "messages,comments"


def subscribe_instagram_webhooks(ig_user_id: str, access_token: str) -> tuple[bool, str]:
  if not ig_user_id or not access_token:
    return False, "شناسه پیج یا توکن خالی است"
  try:
    r = requests.post(
      f"{GRAPH_API}/{ig_user_id}/subscribed_apps",
      headers={"Authorization": f"Bearer {access_token}"},
      params={"subscribed_fields": SUBSCRIBED_FIELDS},
      timeout=15,
    )
    data = r.json()
    if r.status_code == 200 and data.get("success"):
      print(f"[WEBHOOK_SUB] subscribed {ig_user_id} fields={SUBSCRIBED_FIELDS}", flush=True)
      return True, ""
    err = data.get("error") or {}
    msg = err.get("message") or str(data)
    print(f"[WEBHOOK_SUB] failed {ig_user_id}: {msg}", flush=True)
    return False, msg
  except Exception as e:
    print(f"[WEBHOOK_SUB] error {ig_user_id}: {e}", flush=True)
    return False, str(e)


def get_webhook_subscription(ig_user_id: str, access_token: str) -> dict:
  """Return {subscribed: bool, fields: list[str], error: str}."""
  if not ig_user_id or not access_token:
    return {"subscribed": False, "fields": [], "error": "no token"}
  try:
    r = requests.get(
      f"{GRAPH_API}/{ig_user_id}/subscribed_apps",
      headers={"Authorization": f"Bearer {access_token}"},
      timeout=12,
    )
    data = r.json()
    if r.status_code != 200:
      err = (data.get("error") or {}).get("message", str(data))
      return {"subscribed": False, "fields": [], "error": err}
    rows = data.get("data") or []
    fields: list[str] = []
    for row in rows:
      fields.extend(row.get("subscribed_fields") or [])
    fields = sorted(set(fields))
    needed = {f.strip() for f in SUBSCRIBED_FIELDS.split(",")}
    subscribed = needed.issubset(set(fields))
    return {"subscribed": subscribed, "fields": fields, "error": ""}
  except Exception as e:
    return {"subscribed": False, "fields": [], "error": str(e)}
