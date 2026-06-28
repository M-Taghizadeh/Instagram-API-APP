import json
import uuid

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import Flow
from insta_agent.config import Config
from insta_agent.services.flow_engine import parse_nodes

bp = Blueprint("flows", __name__, url_prefix="/flows")
PER_PAGE = Config.PER_PAGE

FLOW_KINDS = {
  "automation": "پاسخ هوشمند",
  "form": "فرم‌ساز",
  "poll": "نظرسنجی",
  "quiz": "آزمون",
  "showcase": "ویترین فروشگاه",
  "followup": "فالوآپ",
}

CHANNELS = {"dm": "دایرکت", "comment": "کامنت"}


def _default_nodes(flow_kind: str) -> list:
  nid = lambda: str(uuid.uuid4())[:8]
  if flow_kind == "form":
    return [
      {"id": nid(), "is_start": True, "type": "text", "data": {"text": "سلام! لطفاً فرم را تکمیل کنید."}, "next": ""},
      {"id": nid(), "type": "collect_text", "data": {"prompt": "نام کامل شما؟", "field": "full_name"}, "next": ""},
      {"id": nid(), "type": "collect_phone", "data": {"prompt": "شماره تماس؟", "field": "phone"}, "next": ""},
      {"id": nid(), "type": "save_contact", "data": {}, "next": ""},
      {"id": nid(), "type": "text", "data": {"text": "ممنون! اطلاعات شما ثبت شد."}, "next": ""},
    ]
  if flow_kind == "poll":
    return [
      {"id": nid(), "is_start": True, "type": "poll", "data": {
        "question": "نظر شما درباره محصول ما؟",
        "field": "poll_answer",
        "options": [{"title": "عالی"}, {"title": "خوب"}, {"title": "متوسط"}],
      }, "next": ""},
      {"id": nid(), "type": "text", "data": {"text": "ممنون از شرکت در نظرسنجی!"}, "next": ""},
    ]
  if flow_kind == "quiz":
    return [
      {"id": nid(), "is_start": True, "type": "quiz", "data": {
        "question": "پایتخت ایران کجاست؟",
        "field": "quiz_score",
        "options": [{"title": "تهران", "payload": "tehran"}, {"title": "اصفهان", "payload": "isfahan"}],
        "correct": {"answer": "tehran", "values": ["tehran", "تهران"]},
      }, "next": ""},
      {"id": nid(), "type": "text", "data": {"text": "آزمون تمام شد!"}, "next": ""},
    ]
  if flow_kind == "showcase":
    return [
      {"id": nid(), "is_start": True, "type": "carousel", "data": {
        "elements": [
          {"title": "محصول ۱", "subtitle": "توضیح کوتاه", "image_url": "", "url": "https://example.com",
           "buttons": [{"title": "خرید", "type": "url", "url": "https://example.com"}]},
          {"title": "محصول ۲", "subtitle": "توضیح کوتاه", "image_url": "", "url": "https://example.com",
           "buttons": [{"title": "خرید", "type": "url", "url": "https://example.com"}]},
        ]
      }, "next": ""},
    ]
  if flow_kind == "followup":
    return [
      {"id": nid(), "is_start": True, "type": "text", "data": {"text": "سلام! چطور می‌تونم کمکتون کنم؟"}, "next": ""},
      {"id": nid(), "type": "delay", "data": {"minutes": 60, "followup_payload": {"type": "text", "text": "هنوز سوالی دارید؟"}}, "next": ""},
    ]
  # automation default
  return [
    {"id": nid(), "is_start": True, "type": "text", "data": {"text": "سلام! پیام شما دریافت شد."}, "next": ""},
  ]


def _link_nodes(nodes: list):
  for i, n in enumerate(nodes):
    if i < len(nodes) - 1 and not n.get("next"):
      n["next"] = nodes[i + 1]["id"]


@bp.route("")
@login_required
def flow_list():
  q = request.args.get("q", "").strip()
  kind = request.args.get("kind", "")
  page = request.args.get("page", 1, type=int)
  query = Flow.query.filter_by(user_id=current_user.id)
  if q:
    query = query.filter(Flow.name.ilike(f"%{q}%") | Flow.trigger.ilike(f"%{q}%"))
  if kind:
    query = query.filter_by(flow_kind=kind)
  pagination = query.order_by(Flow.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
  return render_template("flows.html", pagination=pagination, q=q, kind=kind, flow_kinds=FLOW_KINDS)


def _parse_nodes_from_form(raw: str) -> list | None:
  try:
    nodes = json.loads(raw or "[]")
    if isinstance(nodes, list):
      return nodes
  except json.JSONDecodeError:
    pass
  return None


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_flow():
  if request.method == "POST":
    kind = request.form.get("flow_kind", "automation")
    channel = request.form.get("channel", "dm")
    nodes = _parse_nodes_from_form(request.form.get("nodes_json", "[]"))
    if nodes is None:
      flash("فرمت نودهای فلو نامعتبر است.", "error")
      return render_template(
        "flow_form.html",
        flow=None,
        flow_kinds=FLOW_KINDS,
        channels=CHANNELS,
        nodes_for_editor=[],
      )
    if not nodes:
      flash("حداقل یک نود در ویرایشگر بسازید.", "error")
      return render_template(
        "flow_form.html",
        flow=None,
        flow_kinds=FLOW_KINDS,
        channels=CHANNELS,
        nodes_for_editor=[],
      )
    flow = Flow(
      user_id=current_user.id,
      name=request.form.get("name", "فلو جدید").strip(),
      description=request.form.get("description", "").strip(),
      channel=channel,
      flow_kind=kind,
      trigger=request.form.get("trigger", "").strip(),
      match_type=request.form.get("match_type", "contains"),
      post_id=request.form.get("post_id", "").strip(),
      nodes_json=json.dumps(nodes, ensure_ascii=False),
      is_active=True,
    )
    db.session.add(flow)
    db.session.commit()
    flash("فلو ساخته شد.", "success")
    return redirect(url_for("flows.edit_flow", flow_id=flow.id))
  return render_template(
    "flow_form.html",
    flow=None,
    flow_kinds=FLOW_KINDS,
    channels=CHANNELS,
    nodes_for_editor=[],
  )


@bp.route("/<flow_id>/edit", methods=["GET", "POST"])
@login_required
def edit_flow(flow_id):
  flow = Flow.query.filter_by(id=flow_id, user_id=current_user.id).first_or_404()
  if request.method == "POST":
    flow.name = request.form.get("name", "").strip()
    flow.description = request.form.get("description", "").strip()
    flow.channel = request.form.get("channel", "dm")
    flow.flow_kind = request.form.get("flow_kind", "automation")
    flow.trigger = request.form.get("trigger", "").strip()
    flow.match_type = request.form.get("match_type", "contains")
    flow.post_id = request.form.get("post_id", "").strip()
    nodes_raw = request.form.get("nodes_json", "[]")
    nodes = _parse_nodes_from_form(nodes_raw)
    if nodes is None:
      flash("فرمت JSON نودها نامعتبر است.", "error")
      return render_template(
        "flow_form.html",
        flow=flow,
        flow_kinds=FLOW_KINDS,
        channels=CHANNELS,
        nodes_for_editor=parse_nodes(flow),
      )
    if not nodes:
      flash("حداقل یک نود در ویرایشگر بسازید.", "error")
      return render_template(
        "flow_form.html",
        flow=flow,
        flow_kinds=FLOW_KINDS,
        channels=CHANNELS,
        nodes_for_editor=parse_nodes(flow),
      )
    flow.nodes_json = json.dumps(nodes, ensure_ascii=False)
    db.session.commit()
    flash("فلو ذخیره شد.", "success")
    return redirect(url_for("flows.flow_list"))
  nodes = parse_nodes(flow)
  return render_template(
    "flow_form.html",
    flow=flow,
    flow_kinds=FLOW_KINDS,
    channels=CHANNELS,
    nodes_for_editor=nodes,
  )


@bp.route("/<flow_id>/toggle", methods=["POST"])
@login_required
def toggle_flow(flow_id):
  flow = Flow.query.filter_by(id=flow_id, user_id=current_user.id).first_or_404()
  flow.is_active = not flow.is_active
  db.session.commit()
  return jsonify(active=flow.is_active)


@bp.route("/<flow_id>/delete", methods=["POST"])
@login_required
def delete_flow(flow_id):
  flow = Flow.query.filter_by(id=flow_id, user_id=current_user.id).first_or_404()
  db.session.delete(flow)
  db.session.commit()
  flash("فلو حذف شد.", "success")
  return redirect(url_for("flows.flow_list"))
