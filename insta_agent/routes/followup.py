import json
from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import ScheduledMessage, Contact
from insta_agent.config import Config
from insta_agent.utils import now_tehran

bp = Blueprint("followup", __name__, url_prefix="/followup")
PER_PAGE = Config.PER_PAGE


@bp.route("")
@login_required
def followup_list():
  page = request.args.get("page", 1, type=int)
  status = request.args.get("status", "")
  query = ScheduledMessage.query.filter_by(user_id=current_user.id)
  if status:
    query = query.filter_by(status=status)
  pagination = query.order_by(ScheduledMessage.send_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
  pending = ScheduledMessage.query.filter_by(user_id=current_user.id, status="pending").count()
  return render_template("followup.html", pagination=pagination, status=status, pending=pending)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_followup():
  if request.method == "POST":
    ig_user_id = request.form.get("ig_user_id", "").strip()
    message = request.form.get("message", "").strip()
    hours = int(request.form.get("hours", 1) or 1)
    if not ig_user_id or not message:
      flash("شناسه کاربر و پیام الزامی است.", "error")
      return render_template("followup_form.html")
    sm = ScheduledMessage(
      user_id=current_user.id,
      ig_user_id=ig_user_id,
      ig_username=request.form.get("ig_username", "").strip(),
      payload_json=json.dumps({"type": "text", "text": message}, ensure_ascii=False),
      send_at=now_tehran() + timedelta(hours=hours),
      note="manual followup",
    )
    db.session.add(sm)
    db.session.commit()
    flash("پیام زمان‌بندی شد.", "success")
    return redirect(url_for("followup.followup_list"))
  return render_template("followup_form.html")


@bp.route("/<int:job_id>/cancel", methods=["POST"])
@login_required
def cancel_followup(job_id):
  job = ScheduledMessage.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
  if job.status == "pending":
    job.status = "cancelled"
    db.session.commit()
    flash("لغو شد.", "success")
  return redirect(url_for("followup.followup_list"))
