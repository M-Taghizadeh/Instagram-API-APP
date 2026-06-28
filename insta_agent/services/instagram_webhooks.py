"""Subscribe Instagram professional accounts to Meta app webhooks."""

from insta_agent.services.instagram_http import GRAPH_API, api_message, get_no_redirect, post_no_redirect

SUBSCRIBED_FIELDS = "messages,comments"


def subscribe_instagram_webhooks(ig_user_id: str, access_token: str) -> tuple[bool, str]:
  if not ig_user_id or not access_token:
    return False, "شناسه پیج یا توکن خالی است"

  params = {"subscribed_fields": SUBSCRIBED_FIELDS, "access_token": access_token}
  errors: list[str] = []

  for url in (f"{GRAPH_API}/me/subscribed_apps", f"{GRAPH_API}/{ig_user_id}/subscribed_apps"):
    for label, req in (
      ("post-query", lambda u=url: post_no_redirect(u, params=params)),
      ("post-bearer", lambda u=url: post_no_redirect(
        u, headers={"Authorization": f"Bearer {access_token}"}, params={"subscribed_fields": SUBSCRIBED_FIELDS}
      )),
    ):
      try:
        r = req()
        data = r.json()
        if r.status_code == 200 and data.get("success"):
          print(f"[WEBHOOK_SUB] ok {label} {url}", flush=True)
          return True, ""
        msg = api_message(data)
        errors.append(msg)
        print(f"[WEBHOOK_SUB] {label} {url} -> {msg}", flush=True)
      except Exception as e:
        errors.append(str(e))
        print(f"[WEBHOOK_SUB] {label} {url} error: {e}", flush=True)

  msg = errors[-1] if errors else "ثبت Webhook ناموفق بود"
  return False, msg


def get_webhook_subscription(ig_user_id: str, access_token: str) -> dict:
  if not ig_user_id or not access_token:
    return {"subscribed": False, "fields": [], "error": "no token"}

  bearer = {"Authorization": f"Bearer {access_token}"}
  params = {"access_token": access_token}
  last_err = ""
  needed = {f.strip() for f in SUBSCRIBED_FIELDS.split(",")}

  for url in (f"{GRAPH_API}/me/subscribed_apps", f"{GRAPH_API}/{ig_user_id}/subscribed_apps"):
    for headers, qparams in ((bearer, None), (None, params)):
      try:
        r = get_no_redirect(url, headers=headers or {}, params=qparams)
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
