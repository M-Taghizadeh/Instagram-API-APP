import json
import os

from flask import Blueprint, request, jsonify
from flask_login import login_required

from insta_agent.extensions import db
from insta_agent.models import User, DmRule, CommentRule, Settings
from insta_agent.db_init import get_settings_for, get_access_token, is_on_cooldown, update_cooldown, log_activity
from insta_agent.services.match import match_text
from insta_agent.services import messaging, instagram_api, flow_engine
from insta_agent.services.subscription_service import has_automation_access
from insta_agent.config import Config

bp = Blueprint("webhook", __name__)
_last_webhook_payload = []


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

    for user in User.query.all():
      if not has_automation_access(user.id):
        continue
      token = get_access_token(user.id)
      dm_rules = DmRule.query.filter_by(user_id=user.id, is_active=True).all()
      com_rules = CommentRule.query.filter_by(user_id=user.id, is_active=True).all()

      for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
          _handle_messaging(event, dm_rules, token, user.id)

        for change in entry.get("changes", []):
          field = change.get("field", "")
          value = change.get("value", {})
          if field == "comments":
            _handle_comment(value, com_rules, token, user.id)
          elif field in ("messages", "messaging"):
            fake_event = {
              "sender": value.get("sender", {}),
              "message": value.get("message", {}),
            }
            _handle_messaging(fake_event, dm_rules, token, user.id)

    return jsonify(ok=True), 200
  except Exception as e:
    import traceback
    print("WEBHOOK ERROR:", e, flush=True)
    print(traceback.format_exc(), flush=True)
    return jsonify(ok=False), 200


def _handle_messaging(event, dm_rules, token, owner_id):
  if "message" not in event:
    return
  sender_id = (event.get("sender") or {}).get("id")
  text = (event.get("message") or {}).get("text", "")
  if not sender_id:
    return

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

  page_id = instagram_api.get_page_ig_id(token)
  if page_id and ig_user_id == page_id:
    return
  if parent_id:
    return

  for rule in rules:
    if rule.post_id and rule.post_id != media_id:
      continue
    if match_text(rule.trigger, text, rule.match_type):
      if is_on_cooldown(owner_id, rule.id, ig_user_id or ""):
        break
      actions = []
      if rule.comment_reply:
        ok = messaging.reply_comment(comment_id, rule.comment_reply, token)
        actions.append("replied_comment" if ok else "comment_failed")
      if rule.dm_response:
        ok2 = messaging.private_reply(comment_id, rule.dm_response, token)
        if ok2:
          actions.append("sent_private_reply")
        else:
          ok3 = messaging.send_text(ig_user_id, rule.dm_response, token)
          actions.append("sent_dm_fallback" if ok3 else "dm_failed")
      rule.fire_count = (rule.fire_count or 0) + 1
      db.session.commit()
      if ig_user_id:
        update_cooldown(owner_id, rule.id, ig_user_id)
      username = instagram_api.get_ig_username(ig_user_id, token) if ig_user_id else ""
      log_activity(owner_id, "comment", rule.id, rule.trigger, ig_user_id or "",
                   "+".join(actions) if actions else "no_action",
                   "ok" if actions else "error", ig_username=username)
      break
