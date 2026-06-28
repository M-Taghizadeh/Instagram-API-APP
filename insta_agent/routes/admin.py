from functools import wraps
import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from insta_agent.extensions import db
from insta_agent.models import (
  User, Plan, Subscription, Payment, IgAccount, Flow, Contact, ActivityLog,
)
from insta_agent.utils import now_tehran
from insta_agent.services.accounting_service import build_report, export_csv, MONTH_NAMES

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
  @wraps(f)
  def wrapped(*args, **kwargs):
    if not current_user.is_authenticated or not current_user.is_admin:
      abort(403)
    return f(*args, **kwargs)
  return wrapped


@bp.route("")
@login_required
@admin_required
def dashboard():
  now = now_tehran()
  total_users = User.query.count()
  total_pages = IgAccount.query.count()
  active_subs = Subscription.query.filter_by(status="active").filter(
    Subscription.expires_at > now
  ).count()
  trial_subs = Subscription.query.filter_by(status="active", is_trial=True).filter(
    Subscription.expires_at > now
  ).count()
  paid_subs = active_subs - trial_subs
  revenue_total = db.session.query(func.coalesce(func.sum(Payment.amount_toman), 0)).filter(
    Payment.status == "paid"
  ).scalar() or 0
  revenue_month = db.session.query(func.coalesce(func.sum(Payment.amount_toman), 0)).filter(
    Payment.status == "paid",
    Payment.verified_at >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
  ).scalar() or 0
  pending_payments = Payment.query.filter_by(status="pending").count()
  total_flows = Flow.query.count()
  total_contacts = Contact.query.count()
  activity_7d = ActivityLog.query.filter(
    ActivityLog.created_at >= now - datetime.timedelta(days=7)
  ).count()

  plan_stats = db.session.query(
    Subscription.plan_slug, func.count(Subscription.id)
  ).filter(
    Subscription.status == "active",
    Subscription.expires_at > now,
    Subscription.is_trial == False,
  ).group_by(Subscription.plan_slug).all()

  recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
  recent_user_rows = []
  for u in User.query.order_by(User.created_at.desc()).limit(10).all():
    ig = IgAccount.query.filter_by(user_id=u.id, is_primary=True).first()
    sub = Subscription.query.filter_by(user_id=u.id, status="active").order_by(
      Subscription.expires_at.desc()
    ).first()
    recent_user_rows.append({"user": u, "ig": ig, "sub": sub})

  return render_template(
    "admin/dashboard.html",
    total_users=total_users,
    total_pages=total_pages,
    active_subs=active_subs,
    trial_subs=trial_subs,
    paid_subs=paid_subs,
    revenue_total=revenue_total,
    revenue_month=revenue_month,
    pending_payments=pending_payments,
    total_flows=total_flows,
    total_contacts=total_contacts,
    activity_7d=activity_7d,
    plan_stats=plan_stats,
    recent_payments=recent_payments,
    recent_user_rows=recent_user_rows,
  )


@bp.route("/plans", methods=["GET", "POST"])
@login_required
@admin_required
def plans():
  plans_list = Plan.query.order_by(Plan.sort_order).all()
  if request.method == "POST":
    for p in plans_list:
      p.price_1m = request.form.get(f"price_1m_{p.slug}", p.price_1m, type=int)
      p.price_6m = request.form.get(f"price_6m_{p.slug}", p.price_6m, type=int)
      p.price_12m = request.form.get(f"price_12m_{p.slug}", p.price_12m, type=int)
      p.is_active = request.form.get(f"active_{p.slug}") == "on"
    db.session.commit()
    flash("قیمت‌ها ذخیره شد.", "success")
    return redirect(url_for("admin.plans"))
  return render_template("admin/plans.html", plans=plans_list)


@bp.route("/users")
@login_required
@admin_required
def users():
  q = request.args.get("q", "").strip()
  query = User.query
  if q:
    query = query.filter(User.username.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
  users_list = query.order_by(User.id.desc()).limit(100).all()
  rows = []
  for u in users_list:
    ig = IgAccount.query.filter_by(user_id=u.id, is_primary=True).first()
    sub = Subscription.query.filter_by(user_id=u.id, status="active").order_by(
      Subscription.expires_at.desc()
    ).first()
    rows.append({"user": u, "ig": ig, "sub": sub})
  return render_template("admin/users.html", rows=rows, q=q)


@bp.route("/payments")
@login_required
@admin_required
def payments():
  return redirect(url_for("admin.accounting", **dict(request.args)))


@bp.route("/accounting")
@login_required
@admin_required
def accounting():
  period = request.args.get("period", "month")
  date_from = request.args.get("date_from", "")
  date_to = request.args.get("date_to", "")
  year = request.args.get("year", type=int)
  month = request.args.get("month", type=int)
  status_filter = request.args.get("status", "")

  report = build_report(period, date_from, date_to, year, month, status_filter)
  years = list(range(now_tehran().year, now_tehran().year - 5, -1))

  return render_template(
    "admin/accounting.html",
    report=report,
    years=years,
    month_names=MONTH_NAMES,
  )


@bp.route("/accounting/export")
@login_required
@admin_required
def accounting_export():
  from flask import Response

  period = request.args.get("period", "month")
  date_from = request.args.get("date_from", "")
  date_to = request.args.get("date_to", "")
  year = request.args.get("year", type=int)
  month = request.args.get("month", type=int)
  status_filter = request.args.get("status", "")

  report = build_report(period, date_from, date_to, year, month, status_filter)
  csv_data = export_csv(report)
  filename = f"accounting_{report['period']}_{now_tehran().strftime('%Y%m%d')}.csv"
  return Response(
    "\ufeff" + csv_data,
    mimetype="text/csv; charset=utf-8",
    headers={"Content-Disposition": f"attachment; filename={filename}"},
  )
