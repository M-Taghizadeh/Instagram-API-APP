from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import ActivityLog, CooldownEntry
from insta_agent.config import Config

bp = Blueprint("activity", __name__)


@bp.route("/activity")
@login_required
def activity_log():
  page = request.args.get("page", 1, type=int)
  ftype = request.args.get("type", "")
  query = ActivityLog.query.filter_by(user_id=current_user.id)
  if ftype in ("dm", "comment", "flow"):
    query = query.filter_by(rule_type=ftype)
  pagination = query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
  total = ActivityLog.query.filter_by(user_id=current_user.id).count()
  return render_template("activity_log.html", pagination=pagination, ftype=ftype, total=total)


@bp.route("/activity/clear", methods=["POST"])
@login_required
def clear_activity():
  ActivityLog.query.filter_by(user_id=current_user.id).delete()
  db.session.commit()
  flash("لاگ‌ها پاک شدند.", "success")
  return redirect(url_for("activity.activity_log"))


@bp.route("/activity/clear-cooldowns", methods=["POST"])
@login_required
def clear_cooldowns():
  deleted = CooldownEntry.query.filter_by(user_id=current_user.id).delete()
  db.session.commit()
  flash(f"کولداون‌ها پاک شدند ({deleted} ردیف).", "success")
  return redirect(url_for("activity.activity_log"))
