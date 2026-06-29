import json
import requests

from insta_agent.config import Config

GRAPH_API = Config.GRAPH_API.rstrip("/")
FB_GRAPH = "https://graph.facebook.com/v25.0"


def apply_placeholders(text: str, comment: dict | None = None, username: str = "") -> str:
  if not text:
    return ""
  uname = (username or "").strip()
  if not uname and comment:
    uname = ((comment.get("from") or {}).get("username") or "").strip()
  display = uname or "دوست"
  return text.replace("{name}", display).replace("{username}", display)


def _api_error_text(r: requests.Response) -> str:
  try:
    err = r.json().get("error", {})
    if isinstance(err, dict):
      msg = err.get("message") or ""
      code = err.get("code")
      sub = err.get("error_subcode")
      return f"{msg} (code={code}, sub={sub})".strip()
  except Exception:
    pass
  return (r.text or "")[:240]


def _post_json(url: str, token: str, payload: dict, label: str) -> tuple[bool, str]:
  last_err = "request_failed"
  for mode in ("bearer", "query"):
    try:
      if mode == "bearer":
        r = requests.post(
          url,
          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
          json=payload,
          timeout=12,
        )
      else:
        r = requests.post(
          url,
          params={"access_token": token},
          json=payload,
          timeout=12,
        )
      print(f"[{label}:{mode}] url={url} status={r.status_code} {r.text[:300]}", flush=True)
      if r.status_code == 200:
        try:
          body = r.json()
          if isinstance(body, dict) and body.get("error"):
            last_err = _api_error_text(r)
            continue
        except Exception:
          pass
        return True, ""
      last_err = _api_error_text(r)
    except Exception as e:
      last_err = str(e)
      print(f"{label} ERROR: {e}", flush=True)
  return False, last_err


def _post_messages(token: str, payload: dict, label: str = "MESSAGE") -> tuple[bool, str]:
  if not token:
    return False, "no_token"
  return _post_json(f"{GRAPH_API}/me/messages", token, payload, label)


def send_text(user_id: str, text: str, token: str) -> bool:
  if not user_id or not token or not text:
    return False
  ok, _ = _post_messages(
    token,
    {"recipient": {"id": str(user_id)}, "message": {"text": text}},
    "SEND_TEXT",
  )
  return ok


def send_media(user_id: str, media_type: str, url: str, token: str) -> bool:
  """media_type: image | video | audio"""
  if not user_id or not token or not url:
    return False
  try:
    r = requests.post(
      f"{GRAPH_API}/me/messages",
      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
      json={
        "recipient": {"id": user_id},
        "message": {"attachment": {"type": media_type, "payload": {"url": url}}},
      },
      timeout=30,
    )
    print(f"[SEND_MEDIA:{media_type}] status={r.status_code} {r.text[:200]}", flush=True)
    return r.status_code == 200
  except Exception as e:
    print(f"MEDIA ERROR: {e}", flush=True)
    return False


def send_quick_replies(user_id: str, text: str, options: list, token: str) -> bool:
  """options: [{title, payload}]"""
  if not user_id or not token:
    return False
  qr = [{"content_type": "text", "title": o["title"][:20], "payload": o.get("payload", o["title"])} for o in options[:13]]
  try:
    r = requests.post(
      f"{GRAPH_API}/me/messages",
      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
      json={
        "recipient": {"id": user_id},
        "message": {"text": text[:1000], "quick_replies": qr},
      },
      timeout=10,
    )
    return r.status_code == 200
  except Exception as e:
    print(f"QUICK_REPLY ERROR: {e}", flush=True)
    return False


def send_generic_carousel(user_id: str, elements: list, token: str) -> bool:
  """ویترین — اسکرول افقی"""
  if not user_id or not token or not elements:
    return False
  els = []
  for el in elements[:10]:
    item = {
      "title": (el.get("title") or "")[:80],
      "subtitle": (el.get("subtitle") or "")[:80],
    }
    if el.get("image_url"):
      item["image_url"] = el["image_url"]
    if el.get("url"):
      item["default_action"] = {"type": "web_url", "url": el["url"]}
    buttons = []
    for btn in (el.get("buttons") or [])[:3]:
      if btn.get("type") == "url" and btn.get("url"):
        buttons.append({"type": "web_url", "url": btn["url"], "title": btn.get("title", "بازدید")[:20]})
      else:
        buttons.append({"type": "postback", "title": btn.get("title", "انتخاب")[:20], "payload": btn.get("payload", "OK")})
    if buttons:
      item["buttons"] = buttons
    els.append(item)
  try:
    r = requests.post(
      f"{GRAPH_API}/me/messages",
      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
      json={
        "recipient": {"id": user_id},
        "message": {"attachment": {"type": "template", "payload": {"template_type": "generic", "elements": els}}},
      },
      timeout=15,
    )
    print(f"[CAROUSEL] status={r.status_code} {r.text[:200]}", flush=True)
    return r.status_code == 200
  except Exception as e:
    print(f"CAROUSEL ERROR: {e}", flush=True)
    return False


def send_button_template(user_id: str, text: str, buttons: list, token: str) -> bool:
  if not user_id or not token:
    return False
  btns = []
  for btn in buttons[:3]:
    if btn.get("type") == "url":
      btns.append({"type": "web_url", "url": btn["url"], "title": btn.get("title", "لینک")[:20]})
    else:
      btns.append({"type": "postback", "title": btn.get("title", "انتخاب")[:20], "payload": btn.get("payload", "OK")})
  try:
    r = requests.post(
      f"{GRAPH_API}/me/messages",
      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
      json={
        "recipient": {"id": user_id},
        "message": {
          "attachment": {
            "type": "template",
            "payload": {"template_type": "button", "text": text[:640], "buttons": btns},
          }
        },
      },
      timeout=10,
    )
    return r.status_code == 200
  except Exception as e:
    print(f"BUTTON ERROR: {e}", flush=True)
    return False


def send_payload(user_id: str, payload: dict, token: str) -> bool:
  """ارسال بر اساس نوع node در فلو"""
  ptype = payload.get("type", "text")
  if ptype == "text":
    return send_text(user_id, payload.get("text", ""), token)
  if ptype in ("image", "video", "audio"):
    return send_media(user_id, ptype, payload.get("url", ""), token)
  if ptype == "carousel":
    return send_generic_carousel(user_id, payload.get("elements", []), token)
  if ptype == "buttons":
    return send_button_template(user_id, payload.get("text", ""), payload.get("buttons", []), token)
  if ptype == "quick_replies":
    return send_quick_replies(user_id, payload.get("text", ""), payload.get("options", []), token)
  return False


def reply_comment(comment_id: str, text: str, token: str) -> bool:
  if not comment_id or not token or not text:
    return False
  ok, err = _post_json(
    f"{GRAPH_API}/{comment_id}/replies",
    token,
    {"message": text[:2200]},
    "COMMENT_REPLY",
  )
  if not ok:
    print(f"COMMENT REPLY FAILED id={comment_id}: {err}", flush=True)
  return ok


def private_reply(comment_id: str, text: str, token: str, ig_account_id: str = "") -> tuple[bool, str]:
  """DM in response to a comment — recipient must be comment_id, not user id."""
  if not comment_id or not token or not text:
    return False, "missing_comment_or_text"

  msg_text = text[:1000]
  payload = {
    "recipient": {"comment_id": str(comment_id)},
    "message": {"text": msg_text},
  }

  endpoints: list[str] = []
  if ig_account_id:
    endpoints.append(f"{GRAPH_API}/{ig_account_id}/messages")
    endpoints.append(f"{FB_GRAPH}/{ig_account_id}/messages")
  endpoints.append(f"{GRAPH_API}/me/messages")
  endpoints.append(f"{FB_GRAPH}/me/messages")

  last_err = ""
  for url in endpoints:
    ok, err = _post_json(url, token, payload, "PRIVATE_REPLY")
    if ok:
      return True, ""
    last_err = err

  for body in ({"message": msg_text}, {"message": {"text": msg_text}}):
    for url in (f"{GRAPH_API}/{comment_id}/private_replies", f"{FB_GRAPH}/{comment_id}/private_replies"):
      ok, err = _post_json(url, token, body, "PRIVATE_REPLY_LEGACY")
      if ok:
        return True, ""
      last_err = err

  return False, last_err or "private_reply_failed"
