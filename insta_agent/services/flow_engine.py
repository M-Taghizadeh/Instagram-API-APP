import json
import re
import uuid
from datetime import timedelta

from insta_agent.extensions import db
from insta_agent.models import Flow, FlowSession, Contact, ScheduledMessage, ActivityLog
from insta_agent.services.match import match_text
from insta_agent.services import messaging
from insta_agent.services.instagram_api import get_ig_username
from insta_agent.utils import now_tehran


def parse_nodes(flow: Flow) -> list:
  try:
    return json.loads(flow.nodes_json or "[]")
  except json.JSONDecodeError:
    return []


def get_node(nodes: list, node_id: str) -> dict | None:
  for n in nodes:
    if n.get("id") == node_id:
      return n
  return None


def first_node(nodes: list) -> dict | None:
  if not nodes:
    return None
  for n in nodes:
    if n.get("is_start"):
      return n
  return nodes[0]


def next_node_id(nodes: list, current_id: str, branch: str = "") -> str | None:
  for n in nodes:
    if n.get("id") == current_id:
      if branch and n.get("branches"):
        return n["branches"].get(branch) or n.get("next")
      return n.get("next")
  return None


def upsert_contact(user_id: int, ig_user_id: str, ig_username: str = "", **fields):
  c = Contact.query.filter_by(user_id=user_id, ig_user_id=ig_user_id).first()
  if not c:
    c = Contact(user_id=user_id, ig_user_id=ig_user_id)
    db.session.add(c)
  if ig_username:
    c.ig_username = ig_username
  for k, v in fields.items():
    if v and hasattr(c, k):
      setattr(c, k, v)
    elif v:
      try:
        custom = json.loads(c.custom_fields_json or "{}")
        custom[k] = v
        c.custom_fields_json = json.dumps(custom, ensure_ascii=False)
      except Exception:
        pass
  c.updated_at = now_tehran()
  db.session.commit()
  return c


def log_flow_activity(user_id, flow, ig_user_id, action, status="ok", ig_username=""):
  log = ActivityLog(
    user_id=user_id, rule_type="flow", rule_id=flow.id,
    rule_name=flow.name, ig_user_id=ig_user_id, ig_username=ig_username,
    action=action, status=status,
  )
  db.session.add(log)
  db.session.commit()


def execute_node(node: dict, ig_user_id: str, token: str, session: FlowSession) -> list:
  """یک node را اجرا کن — لیست actionها برمی‌گرداند"""
  actions = []
  ntype = node.get("type", "text")
  data = node.get("data", {})

  if ntype == "text":
    ok = messaging.send_text(ig_user_id, data.get("text", ""), token)
    actions.append("sent_text" if ok else "text_failed")

  elif ntype in ("image", "video", "audio"):
    ok = messaging.send_media(ig_user_id, ntype, data.get("url", ""), token)
    actions.append(f"sent_{ntype}" if ok else f"{ntype}_failed")

  elif ntype == "carousel":
    ok = messaging.send_generic_carousel(ig_user_id, data.get("elements", []), token)
    actions.append("sent_carousel" if ok else "carousel_failed")

  elif ntype == "buttons":
    ok = messaging.send_button_template(ig_user_id, data.get("text", ""), data.get("buttons", []), token)
    actions.append("sent_buttons" if ok else "buttons_failed")

  elif ntype == "quick_replies":
    ok = messaging.send_quick_replies(ig_user_id, data.get("text", ""), data.get("options", []), token)
    actions.append("sent_quick_replies" if ok else "qr_failed")

  elif ntype == "collect_phone":
    messaging.send_text(ig_user_id, data.get("prompt", "لطفاً شماره تماس خود را ارسال کنید:"), token)
    ctx = json.loads(session.context_json or "{}")
    ctx["awaiting"] = "phone"
    ctx["field"] = data.get("field", "phone")
    session.context_json = json.dumps(ctx, ensure_ascii=False)
    actions.append("awaiting_phone")

  elif ntype == "collect_text":
    messaging.send_text(ig_user_id, data.get("prompt", "لطفاً پاسخ خود را بنویسید:"), token)
    ctx = json.loads(session.context_json or "{}")
    ctx["awaiting"] = "text"
    ctx["field"] = data.get("field", "answer")
    session.context_json = json.dumps(ctx, ensure_ascii=False)
    actions.append("awaiting_text")

  elif ntype == "poll":
    options = [{"title": o.get("title", f"گزینه {i+1}"), "payload": o.get("payload", str(i))}
               for i, o in enumerate(data.get("options", []))]
    ok = messaging.send_quick_replies(ig_user_id, data.get("question", "نظرسنجی:"), options, token)
    ctx = json.loads(session.context_json or "{}")
    ctx["awaiting"] = "poll"
    ctx["poll_field"] = data.get("field", "poll_answer")
    session.context_json = json.dumps(ctx, ensure_ascii=False)
    actions.append("sent_poll" if ok else "poll_failed")

  elif ntype == "quiz":
    options = [{"title": o.get("title", ""), "payload": o.get("payload", o.get("title", ""))}
               for o in data.get("options", [])]
    ok = messaging.send_quick_replies(ig_user_id, data.get("question", ""), options, token)
    ctx = json.loads(session.context_json or "{}")
    ctx["awaiting"] = "quiz"
    ctx["quiz_answers"] = data.get("correct", {})
    ctx["quiz_field"] = data.get("field", "quiz_score")
    session.context_json = json.dumps(ctx, ensure_ascii=False)
    actions.append("sent_quiz" if ok else "quiz_failed")

  elif ntype == "delay":
    minutes = int(data.get("minutes", 1))
    send_at = now_tehran() + timedelta(minutes=minutes)
    next_id = node.get("next", "")
    payload = {"type": "text", "text": data.get("followup_text", "")}
    if next_id:
      # پیام بعدی از node بعدی گرفته می‌شود در scheduler
      pass
    sm = ScheduledMessage(
      user_id=session.user_id,
      ig_user_id=ig_user_id,
      ig_username=session.ig_username,
      payload_json=json.dumps(data.get("followup_payload", payload), ensure_ascii=False),
      send_at=send_at,
      flow_id=session.flow_id,
      note=f"delay from node {node.get('id')}",
    )
    db.session.add(sm)
    actions.append("scheduled_delay")

  elif ntype == "save_contact":
    ctx = json.loads(session.context_json or "{}")
    upsert_contact(session.user_id, ig_user_id, session.ig_username, **ctx.get("collected", {}))
    actions.append("saved_contact")

  return actions


def advance_session(session: FlowSession, nodes: list, branch: str = ""):
  nxt = next_node_id(nodes, session.current_node_id, branch)
  if not nxt:
    session.status = "completed"
    session.current_node_id = ""
  else:
    session.current_node_id = nxt
  session.updated_at = now_tehran()
  db.session.commit()


def run_from_node(flow: Flow, session: FlowSession, token: str, start_id: str | None = None):
  nodes = parse_nodes(flow)
  node_id = start_id or session.current_node_id or (first_node(nodes) or {}).get("id", "")
  if not node_id:
    return []

  all_actions = []
  current_id = node_id
  safety = 0
  while current_id and safety < 20:
    safety += 1
    node = get_node(nodes, current_id)
    if not node:
      break
    session.current_node_id = current_id
    db.session.commit()
    actions = execute_node(node, session.ig_user_id, token, session)
    all_actions.extend(actions)

    # اگر منتظر ورودی کاربر هستیم، متوقف شو
    ctx = json.loads(session.context_json or "{}")
    if ctx.get("awaiting"):
      break

    ntype = node.get("type", "")
    if ntype in ("collect_phone", "collect_text", "poll", "quiz"):
      break

    current_id = next_node_id(nodes, current_id)
    if not current_id:
      session.status = "completed"
      db.session.commit()
      break
    session.current_node_id = current_id

  flow.fire_count = (flow.fire_count or 0) + 1
  db.session.commit()
  return all_actions


def handle_incoming_dm(owner_id: int, ig_user_id: str, text: str, token: str) -> bool:
  """فلوهای فعال را بررسی و اجرا کن"""
  username = get_ig_username(ig_user_id, token)

  # ادامه session فعال
  active = FlowSession.query.filter_by(
    user_id=owner_id, ig_user_id=ig_user_id, status="active"
  ).order_by(FlowSession.updated_at.desc()).first()

  if active:
    ctx = json.loads(active.context_json or "{}")
    awaiting = ctx.get("awaiting")
    if awaiting:
      collected = ctx.get("collected", {})
      if awaiting == "phone":
        phone = re.sub(r"\D", "", text or "")
        if len(phone) >= 10:
          field = ctx.get("field", "phone")
          collected[field] = phone
          upsert_contact(owner_id, ig_user_id, username, phone=phone)
          ctx.pop("awaiting", None)
          ctx["collected"] = collected
          active.context_json = json.dumps(ctx, ensure_ascii=False)
          db.session.commit()
          flow = Flow.query.get(active.flow_id)
          if flow:
            advance_session(active, parse_nodes(flow))
            if active.current_node_id:
              run_from_node(flow, active, token)
          return True
      elif awaiting in ("text", "poll"):
        field = ctx.get("field") or ctx.get("poll_field", "answer")
        collected[field] = text
        ctx.pop("awaiting", None)
        ctx["collected"] = collected
        active.context_json = json.dumps(ctx, ensure_ascii=False)
        db.session.commit()
        flow = Flow.query.get(active.flow_id)
        if flow:
          advance_session(active, parse_nodes(flow))
          if active.current_node_id:
            run_from_node(flow, active, token)
        return True
      elif awaiting == "quiz":
        correct = ctx.get("quiz_answers", {})
        score = ctx.get("score", 0)
        if text in correct.get("values", []) or text == correct.get("answer"):
          score += 1
        ctx["score"] = score
        ctx.pop("awaiting", None)
        ctx.setdefault("collected", {})[ctx.get("quiz_field", "quiz_score")] = str(score)
        active.context_json = json.dumps(ctx, ensure_ascii=False)
        db.session.commit()
        flow = Flow.query.get(active.flow_id)
        if flow:
          advance_session(active, parse_nodes(flow), branch=text)
          if active.current_node_id:
            run_from_node(flow, active, token)
        return True

  # شروع فلو جدید
  flows = Flow.query.filter_by(user_id=owner_id, is_active=True, channel="dm").all()
  for flow in flows:
    if flow.trigger and not match_text(flow.trigger, text, flow.match_type):
      continue
    session = FlowSession(
      id=str(uuid.uuid4()),
      user_id=owner_id,
      flow_id=flow.id,
      ig_user_id=ig_user_id,
      ig_username=username,
      status="active",
    )
    db.session.add(session)
    db.session.commit()
    nodes = parse_nodes(flow)
    start = first_node(nodes)
    if start:
      session.current_node_id = start["id"]
      db.session.commit()
      actions = run_from_node(flow, session, token, start["id"])
      log_flow_activity(owner_id, flow, ig_user_id, "+".join(actions), ig_username=username)
      return True
  return False


def handle_incoming_comment(owner_id: int, comment: dict, token: str) -> bool:
  from insta_agent.services.instagram_api import get_page_ig_id

  text = comment.get("text", "")
  media_id = (comment.get("media") or {}).get("id")
  comment_id = comment.get("id")
  parent_id = comment.get("parent_id")
  ig_user_id = (comment.get("from") or {}).get("id")

  page_id = get_page_ig_id(token)
  if page_id and ig_user_id == page_id:
    return False
  if parent_id:
    return False

  flows = Flow.query.filter_by(user_id=owner_id, is_active=True, channel="comment").all()
  for flow in flows:
    if flow.post_id and flow.post_id != media_id:
      continue
    if flow.trigger and not match_text(flow.trigger, text, flow.match_type):
      continue

    nodes = parse_nodes(flow)
    actions = []
    ig_username = ((comment.get("from") or {}).get("username") or "").strip()
    for node in nodes:
      ntype = node.get("type", "")
      data = node.get("data", {})
      if ntype == "comment_reply":
        body = messaging.apply_placeholders(data.get("text", ""), comment, ig_username)
        ok = messaging.reply_comment(comment_id, body, token)
        actions.append("replied_comment" if ok else "comment_failed")
      elif ntype in ("text", "dm"):
        body = messaging.apply_placeholders(data.get("text", ""), comment, ig_username)
        ok, dm_err = messaging.private_reply(comment_id, body, token, page_id or "")
        actions.append("sent_private_reply" if ok else "dm_failed")
        if not ok:
          print(f"FLOW COMMENT DM FAILED flow={flow.id} comment={comment_id}: {dm_err}", flush=True)
      elif ntype == "carousel":
        intro = data.get("intro", "محصولات ما:")
        ok, _ = messaging.private_reply(comment_id, intro, token, page_id or "")
        if ok and ig_user_id:
          messaging.send_generic_carousel(ig_user_id, data.get("elements", []), token)
        actions.append("sent_showcase" if ok else "dm_failed")

    flow.fire_count = (flow.fire_count or 0) + 1
    db.session.commit()
    username = get_ig_username(ig_user_id, token) if ig_user_id else ""
    log_flow_activity(owner_id, flow, ig_user_id or "", "+".join(actions), ig_username=username)
    return True
  return False
