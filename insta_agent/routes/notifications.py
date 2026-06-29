from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import Notification
from insta_agent.utils import now_tehran
from insta_agent.services.notification_service import (
  list_notifications, unread_count, mark_all_read, meta_roles_url,
)

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.route("")
@login_required
def inbox():
  items = list_notifications(current_user.id)
  return render_template(
    "notifications/inbox.html",
    items=items,
    unread=unread_count(current_user.id),
    meta_roles_url=meta_roles_url(),
  )


@bp.route("/<int:nid>/read")
@login_required
def read_one(nid: int):
  item = Notification.query.filter_by(id=nid, user_id=current_user.id).first()
  if not item:
    flash("اعلان یافت نشد.", "error")
    return redirect(url_for("notifications.inbox"))
  action = item.action_url
  if not item.read_at:
    item.read_at = now_tehran()
    db.session.commit()
  if action:
    return redirect(action)
  return redirect(url_for("auth.onboarding"))


@bp.route("/read-all", methods=["POST"])
@login_required
def read_all():
  n = mark_all_read(current_user.id)
  flash(f"{n} اعلان خوانده شد.", "success")
  return redirect(url_for("notifications.inbox"))
