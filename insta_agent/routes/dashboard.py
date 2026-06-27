import json
import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from insta_agent.config import Config
from insta_agent.models import DmRule, CommentRule, ActivityLog, Flow, Contact, ScheduledMessage
from insta_agent.db_init import get_settings
from insta_agent.utils import now_tehran

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
  uid = current_user.id
  dm_count = DmRule.query.filter_by(user_id=uid).count()
  comment_count = CommentRule.query.filter_by(user_id=uid).count()
  flow_count = Flow.query.filter_by(user_id=uid).count()
  contact_count = Contact.query.filter_by(user_id=uid).count()
  dm_active = DmRule.query.filter_by(user_id=uid, is_active=True).count()
  cm_active = CommentRule.query.filter_by(user_id=uid, is_active=True).count()
  flow_active = Flow.query.filter_by(user_id=uid, is_active=True).count()
  s = get_settings()
  ig = current_user.primary_ig_account
  token_set = bool(s.access_token or (ig and ig.access_token))
  recent_dm = DmRule.query.filter_by(user_id=uid).order_by(DmRule.created_at.desc()).limit(3).all()
  recent_cm = CommentRule.query.filter_by(user_id=uid).order_by(CommentRule.created_at.desc()).limit(3).all()
  recent_flows = Flow.query.filter_by(user_id=uid).order_by(Flow.created_at.desc()).limit(3).all()

  seven_days_ago = now_tehran() - datetime.timedelta(days=7)
  total_fires = ActivityLog.query.filter(
    ActivityLog.user_id == uid, ActivityLog.created_at >= seven_days_ago
  ).count()
  recent_logs = ActivityLog.query.filter_by(user_id=uid).order_by(ActivityLog.created_at.desc()).limit(5).all()
  pending_followups = ScheduledMessage.query.filter_by(user_id=uid, status="pending").count()

  chart_labels, chart_data = [], []
  for i in range(6, -1, -1):
    day = now_tehran() - datetime.timedelta(days=i)
    label = f"{day.month}/{day.day}"
    count = ActivityLog.query.filter(
      ActivityLog.user_id == uid,
      ActivityLog.created_at >= day.replace(hour=0, minute=0, second=0),
      ActivityLog.created_at < day.replace(hour=23, minute=59, second=59),
    ).count()
    chart_labels.append(label)
    chart_data.append(count)

  return render_template(
    "dashboard.html",
    dm_count=dm_count, comment_count=comment_count, flow_count=flow_count,
    contact_count=contact_count, dm_active=dm_active, cm_active=cm_active,
    flow_active=flow_active, token_set=token_set,
    ig_account=ig, recent_dm=recent_dm, recent_cm=recent_cm,
    recent_flows=recent_flows,
    webhook_url=request.url_root + "webhook",
    total_fires=total_fires, recent_logs=recent_logs,
    pending_followups=pending_followups,
    chart_labels=json.dumps(chart_labels),
    chart_data=json.dumps(chart_data),
  )
