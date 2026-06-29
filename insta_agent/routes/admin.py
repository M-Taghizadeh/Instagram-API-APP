from functools import wraps
import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from insta_agent.extensions import db
from insta_agent.models import (
  User, Plan, Subscription, Payment, IgAccount, Flow, Contact, ActivityLog,
)
from insta_agent.utils import now_tehran, parse_jalali_date, format_jalali, jalali_years, add_jalali_months
from insta_agent.services.subscription_service import (
  admin_grant_subscription, admin_deactivate_subscriptions, plan_for_followers,
)
from insta_agent.services.accounting_service import build_report, export_csv, MONTH_NAMES
from insta_agent.config import Config
from insta_agent.services.instagram_oauth import oauth_configured, oauth_status
from insta_agent.services.tester_gate import count_tester_slots_used, beta_gate_enabled
from insta_agent.services.app_settings_service import set_beta_tester_gate

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
  now = now_tehran()
  rows = []
  for u in users_list:
    ig = IgAccount.query.filter_by(user_id=u.id, is_primary=True).first()
    sub = Subscription.query.filter_by(user_id=u.id, status="active").filter(
      Subscription.expires_at > now
    ).order_by(Subscription.expires_at.desc()).first()
    if not sub:
      sub = Subscription.query.filter_by(user_id=u.id).order_by(
        Subscription.expires_at.desc()
      ).first()
    sub_live = bool(sub and sub.status == "active" and sub.expires_at and sub.expires_at > now)
    rows.append({"user": u, "ig": ig, "sub": sub, "sub_live": sub_live})
  return render_template("admin/users.html", rows=rows, q=q)


@bp.route("/users/<int:user_id>/subscription", methods=["GET", "POST"])
@login_required
@admin_required
def user_subscription(user_id):
  target = User.query.get_or_404(user_id)
  plans = Plan.query.order_by(Plan.sort_order).all()
  now = now_tehran()

  active_sub = Subscription.query.filter_by(user_id=user_id, status="active").filter(
    Subscription.expires_at > now
  ).order_by(Subscription.expires_at.desc()).first()
  history = Subscription.query.filter_by(user_id=user_id).order_by(
    Subscription.created_at.desc()
  ).limit(30).all()

  if request.method == "POST":
    action = request.form.get("action", "save")

    if action == "deactivate":
      n = admin_deactivate_subscriptions(user_id)
      flash(f"اشتراک کاربر غیرفعال شد ({n} مورد).", "success")
      return redirect(url_for("admin.user_subscription", user_id=user_id))

    plan_slug = request.form.get("plan_slug", "").strip()
    period_months = request.form.get("period_months", 1, type=int)
    is_trial = request.form.get("is_trial") == "1"

    starts = parse_jalali_date(request.form.get("starts_at", ""))
    if not starts:
      starts = now.replace(hour=0, minute=0, second=0, microsecond=0)

    expires = parse_jalali_date(request.form.get("expires_at", ""))
    if not expires:
      flash("تاریخ انقضا نامعتبر است — فرمت شمسی: ۱۴۰۴/۰۶/۱۵", "error")
      return redirect(url_for("admin.user_subscription", user_id=user_id))

    expires = expires.replace(hour=23, minute=59, second=59)
    if expires <= starts:
      flash("تاریخ انقضا باید بعد از تاریخ شروع باشد.", "error")
      return redirect(url_for("admin.user_subscription", user_id=user_id))

    admin_grant_subscription(
      user_id=user_id,
      plan_slug=plan_slug,
      starts_at=starts,
      expires_at=expires,
      period_months=period_months,
      is_trial=is_trial,
    )
    flash("پلن کاربر ذخیره و فعال شد.", "success")
    return redirect(url_for("admin.user_subscription", user_id=user_id))

  default_starts = format_jalali(active_sub.starts_at if active_sub else now)
  ig = IgAccount.query.filter_by(user_id=user_id, is_primary=True).first()
  if ig and ig.access_token:
    from insta_agent.services.instagram_profile import sync_ig_account_profile
    sync_ig_account_profile(ig)
    try:
      db.session.commit()
    except Exception:
      db.session.rollback()

  followers = (ig.follower_count or 0) if ig else 0
  suggested = plan_for_followers(followers)

  if active_sub:
    default_expires = format_jalali(active_sub.expires_at)
    default_plan = active_sub.plan_slug
    default_period = active_sub.period_months or 1
    default_trial = active_sub.is_trial
  else:
    default_expires = format_jalali(add_jalali_months(now, 1))
    default_plan = suggested.slug if suggested else (plans[0].slug if plans else "10k")
    default_period = 1
    default_trial = False

  return render_template(
    "admin/user_subscription.html",
    target=target,
    ig=ig,
    plans=plans,
    active_sub=active_sub,
    history=history,
    default_starts=default_starts,
    default_expires=default_expires,
    default_plan=default_plan,
    default_period=default_period,
    default_trial=default_trial,
    suggested_plan=suggested,
    followers=followers,
  )


@bp.route("/integrations")
@login_required
@admin_required
def integrations():
  oauth = oauth_status()
  return render_template(
    "admin/integrations.html",
    oauth=oauth,
    oauth_ready=oauth_configured(),
    meta_app_id=Config.META_APP_ID,
    oauth_redirect=Config.OAUTH_REDIRECT_URI,
    verify_token=Config.VERIFY_TOKEN,
    webhook_url=url_for("webhook.webhook", _external=True),
    oauth_status_url=url_for("oauth.oauth_debug_status"),
    beta_gate=beta_gate_enabled(),
    beta_tester_slots=Config.BETA_TESTER_SLOTS,
    env_beta_default=Config.BETA_TESTER_GATE,
  )


@bp.route("/integrations/beta-gate", methods=["POST"])
@login_required
@admin_required
def toggle_beta_gate():
  enabled = request.form.get("enabled") == "1"
  set_beta_tester_gate(enabled)
  if enabled:
    flash("حالت بتا فعال شد — کاربران از صف Tester و ویزارد ۳ مرحله‌ای استفاده می‌کنند.", "success")
  else:
    flash("اتصال مستقیم فعال شد — کاربران مستقیم دکمه «اتصال پیج اینستاگرام» را می‌بینند.", "success")
  return redirect(url_for("admin.integrations"))


@bp.route("/activation", methods=["GET", "POST"])
@login_required
@admin_required
def activation():
  if request.method == "POST":
    user_id = request.form.get("user_id", type=int)
    action = request.form.get("action", "")
    target = User.query.get(user_id)
    if not target or target.is_admin:
      flash("کاربر یافت نشد.", "error")
      return redirect(url_for("admin.activation"))

    if action == "invited":
      if (target.tester_status or "") not in ("pending",):
        flash("فقط درخواست‌های در انتظار را می‌توان به «دعوت فرستاده» تغییر داد.", "error")
      else:
        target.tester_status = "invited"
        db.session.commit()
        flash(f"@{target.ig_username_requested} — وضعیت به «دعوت فرستاده» تغییر کرد.", "success")
    elif action == "ready":
      if (target.tester_status or "") not in ("pending", "invited"):
        flash("این وضعیت قابل تأیید نیست.", "error")
      else:
        target.tester_status = "ready"
        target.tester_ready_at = now_tehran()
        db.session.commit()
        flash(f"@{target.ig_username_requested} — آماده اتصال است.", "success")
    elif action == "reset":
      target.tester_status = "none"
      target.ig_username_requested = ""
      target.tester_requested_at = None
      target.tester_ready_at = None
      db.session.commit()
      flash("درخواست ریست شد.", "success")
    return redirect(url_for("admin.activation"))

  queue = User.query.filter(
    User.is_admin == False,
    User.tester_status.in_(("pending", "invited", "ready")),
  ).order_by(User.tester_requested_at.asc(), User.id.asc()).all()

  connected = User.query.filter_by(tester_status="connected", is_admin=False).count()
  pending_count = User.query.filter_by(tester_status="pending", is_admin=False).count()

  return render_template(
    "admin/activation.html",
    queue=queue,
    slots_used=count_tester_slots_used(),
    slots_max=Config.BETA_TESTER_SLOTS,
    pending_count=pending_count,
    connected_count=connected,
    beta_gate=beta_gate_enabled(),
    meta_roles_url="https://developers.facebook.com/apps/",
  )


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
  years = jalali_years(6)

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
