import json
import os
import time

from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import User, IgAccount, DmRule, CommentRule, Settings
from insta_agent.db_init import get_settings_for, get_access_token, is_on_cooldown, update_cooldown, log_activity
from insta_agent.services.match import match_text
from insta_agent.services import messaging, instagram_api, flow_engine
from insta_agent.services.subscription_service import has_automation_access
from insta_agent.config import Config

bp = Blueprint("webhook", __name__)
_last_webhook_payload = []
_seen_message_keys: dict[str, float] = {}


def _webhook_message_key(event: dict) -> str:
  msg = event.get("message") or {}
  mid = msg.get("mid") or msg.get("id") or ""
  if mid:
    return str(mid)
  sender = (event.get("sender") or {}).get("id", "")
  ts = str(event.get("timestamp", ""))
  text = (msg.get("text") or "")[:120]
  return f"{sender}:{ts}:{text}"


def _is_duplicate_webhook_event(key: str) -> bool:
  if not key:
    return False
  now = time.time()
  cutoff = now - 300
  stale = [k for k, t in _seen_message_keys.items() if t < cutoff]
  for k in stale:
    del _seen_message_keys[k]
  if key in _seen_message_keys:
    return True
  _seen_message_keys[key] = now
  if len(_seen_message_keys) > 2000:
    oldest = sorted(_seen_message_keys, key=_seen_message_keys.get)[:500]
    for k in oldest:
      del _seen_message_keys[k]
  return False


@bp.route("/webhook", methods=["GET"])
def verify_webhook():
  incoming_token = request.args.get("hub.verify_token", "")
  incoming_challenge = request.args.get("hub.challenge", "")
  verify_tok = Config.VERIFY_TOKEN
  if not verify_tok:
    first_user = User.query.first()
    if first_user:
      s = Settings.query.filter_by(user_id=first_user.id).first()
      if s:
        verify_tok = s.verify_token
  if incoming_token == verify_tok:
    return incoming_challenge, 200
  return "fail", 403


@bp.route("/debug/webhook")
@login_required
def debug_webhook():
  if not current_user.is_admin:
    abort(403)
  return jsonify(payloads=_last_webhook_payload)


@bp.route("/webhook", methods=["POST"])
def webhook():
  try:
    data = request.get_json(force=True, silent=True)
    print("\n===== WEBHOOK =====", flush=True)
    print(json.dumps(data, indent=2, ensure_ascii=False), flush=True)
    if not data:
      return jsonify(ok=True), 200

    _last_webhook_payload.append(data)
    if len(_last_webhook_payload) > 5:
      _last_webhook_payload.pop(0)

    entries = data.get("entry", [])
    print(f"WEBHOOK object={data.get('object', '')} entries={len(entries)}", flush=True)

    for entry in entries:
      entry_id = str(entry.get("id", ""))
      ig = IgAccount.query.filter_by(ig_user_id=entry_id).first() if entry_id else None
      if not ig:
        print(f"WEBHOOK skip: unknown entry.id={entry_id}", flush=True)
        continue
      if not has_automation_access(ig.user_id):
        print(f"WEBHOOK skip: user={ig.user_id} (@{ig.username}) no subscription/trial", flush=True)
        continue
      token = ig.access_token or get_access_token(ig.user_id)
      if not token:
        print(f"WEBHOOK skip: user={ig.user_id} (@{ig.username}) no token", flush=True)
        continue

      print(f"WEBHOOK route → user={ig.user_id} @{ig.username} entry={entry_id}", flush=True)
      dm_rules = DmRule.query.filter_by(user_id=ig.user_id, is_active=True).all()
      com_rules = CommentRule.query.filter_by(user_id=ig.user_id, is_active=True).all()
      page_ids = instagram_api.page_sender_ids(token, ig.ig_user_id, entry_id)

      for event in entry.get("messaging", []):
        _handle_messaging(event, dm_rules, token, ig.user_id, page_ids)

      for change in entry.get("changes", []):
        field = change.get("field", "")
        value = change.get("value", {})
        if field == "comments":
          _handle_comment(value, com_rules, token, ig.user_id)
        elif field in ("messages", "messaging"):
          fake_event = {
            "sender": value.get("sender", {}),
            "recipient": value.get("recipient", {}),
            "message": value.get("message", {}),
            "timestamp": value.get("timestamp"),
            "is_echo": value.get("is_echo"),
          }
          _handle_messaging(fake_event, dm_rules, token, ig.user_id, page_ids)

    return jsonify(ok=True), 200
  except Exception as e:
    import traceback
    print("WEBHOOK ERROR:", e, flush=True)
    print(traceback.format_exc(), flush=True)
    return jsonify(ok=False), 200


def _handle_messaging(event, dm_rules, token, owner_id, page_ids: set[str]):
  if "message" not in event:
    return
  if instagram_api.is_outbound_dm_event(event, page_ids):
    sender_id = (event.get("sender") or {}).get("id", "")
    print(f"WEBHOOK skip outbound/page sender={sender_id}", flush=True)
    return

  sender_id = (event.get("sender") or {}).get("id")
  if not sender_id:
    return

  msg_key = _webhook_message_key(event)
  if _is_duplicate_webhook_event(msg_key):
    print(f"WEBHOOK skip duplicate message key={msg_key[:80]}", flush=True)
    return

  text = (event.get("message") or {}).get("text", "") or ""

  # اول فلوهای پیشرفته
  if flow_engine.handle_incoming_dm(owner_id, sender_id, text, token):
    return

  for rule in dm_rules:
    if match_text(rule.trigger, text, rule.match_type):
      if is_on_cooldown(owner_id, rule.id, sender_id):
        break
      ok = messaging.send_text(sender_id, rule.response, token)
      rule.fire_count = (rule.fire_count or 0) + 1
      db.session.commit()
      update_cooldown(owner_id, rule.id, sender_id)
      username = instagram_api.get_ig_username(sender_id, token)
      log_activity(owner_id, "dm", rule.id, rule.trigger, sender_id,
                   "sent_dm", "ok" if ok else "error", ig_username=username)
      break


def _handle_comment(comment, rules, token, owner_id):
  if flow_engine.handle_incoming_comment(owner_id, comment, token):
    return

  text = comment.get("text", "")
  media_id = (comment.get("media") or {}).get("id")
  comment_id = comment.get("id")
  parent_id = comment.get("parent_id")
  ig_user_id = (comment.get("from") or {}).get("id")
  ig_username = ((comment.get("from") or {}).get("username") or "").strip()

  page_id = instagram_api.get_page_ig_id(token)
  if page_id and ig_user_id == page_id:
    return
  if parent_id:
    return
  if not comment_id:
    print("COMMENT skip: missing comment_id", flush=True)
    return

  for rule in rules:
    if rule.post_id and rule.post_id != media_id:
      continue
    if match_text(rule.trigger, text, rule.match_type):
      if is_on_cooldown(owner_id, rule.id, ig_user_id or ""):
        break
      actions = []
      dm_note = ""
      dm_text = messaging.apply_placeholders((rule.dm_response or "").strip(), comment, ig_username)
      comment_text = messaging.apply_placeholders((rule.comment_reply or "").strip(), comment, ig_username)

      # Private reply first — Meta allows one DM per comment via comment_id.
      if dm_text:
        ok2, dm_err = messaging.private_reply(comment_id, dm_text, token, page_id or "")
        if ok2:
          actions.append("sent_private_reply")
        else:
          actions.append("dm_failed")
          dm_note = dm_err
          print(
            f"COMMENT DM FAILED rule={rule.id} comment={comment_id} user={ig_user_id}: {dm_err}",
            flush=True,
          )
      elif (rule.dm_response or "").strip():
        actions.append("dm_failed")
        dm_note = "empty_dm_after_placeholders"

      if comment_text:
        ok = messaging.reply_comment(comment_id, comment_text, token)
        actions.append("replied_comment" if ok else "comment_failed")

      rule.fire_count = (rule.fire_count or 0) + 1
      db.session.commit()
      if ig_user_id:
        update_cooldown(owner_id, rule.id, ig_user_id)
      if not ig_username and ig_user_id:
        ig_username = instagram_api.get_ig_username(ig_user_id, token)

      status = "ok"
      if not actions or "comment_failed" in actions or "dm_failed" in actions:
        status = "error"
      elif dm_text and "sent_private_reply" not in actions:
        status = "error"

      log_activity(owner_id, "comment", rule.id, rule.trigger, ig_user_id or "",
                   "+".join(actions) if actions else "no_action",
                   status, note=dm_note, ig_username=ig_username)
      break
