from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user, login_user

from insta_agent.extensions import db
from insta_agent.models import Payment, Plan, User
from insta_agent.services import zarinpal
from insta_agent.services.subscription_service import (
  get_plans, get_plan, subscription_status,
  validate_plan_for_user, activate_paid_subscription, pricing_context_for_user,
)
from insta_agent.utils import now_tehran

bp = Blueprint("billing", __name__, url_prefix="/billing")


@bp.route("/pricing")
@login_required
def pricing():
  plans = get_plans()
  ctx = pricing_context_for_user(current_user.id)
  return render_template(
    "pricing.html",
    plans=plans,
    sub_info=ctx["sub_info"],
    pricing_followers=ctx["followers"],
    suggested_plan=ctx["suggested_plan"],
    suggested_slug=ctx["suggested_slug"],
    has_page=ctx["has_page"],
    zarinpal_ready=zarinpal.is_configured(),
  )


@bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
  plan_slug = request.form.get("plan_slug", "").strip()
  period = request.form.get("period", "1", type=int)
  if period not in (1, 6, 12):
    flash("دوره اشتراک نامعتبر است.", "error")
    return redirect(url_for("billing.pricing"))

  ok, msg = validate_plan_for_user(current_user.id, plan_slug)
  if not ok:
    flash(msg, "error")
    return redirect(url_for("billing.pricing"))

  plan = get_plan(plan_slug)
  amount = plan.price_for_period(period)
  if amount <= 0:
    flash("قیمت پلن تنظیم نشده.", "error")
    return redirect(url_for("billing.pricing"))

  if not zarinpal.is_configured():
    flash("درگاه پرداخت هنوز تنظیم نشده — با پشتیبانی تماس بگیر.", "error")
    return redirect(url_for("billing.pricing"))

  payment = Payment(
    user_id=current_user.id,
    plan_slug=plan_slug,
    period_months=period,
    amount_toman=amount,
    status="pending",
  )
  db.session.add(payment)
  db.session.commit()

  callback = url_for("billing.callback", _external=True)
  desc = f"اشتراک محتوام — پلن {plan.name} — {period} ماه"
  try:
    result = zarinpal.request_payment(amount, callback, desc)
    payment.authority = result["authority"]
    db.session.commit()
    return redirect(result["url"])
  except Exception as e:
    payment.status = "failed"
    db.session.commit()
    flash(f"خطا در اتصال به درگاه: {e}", "error")
    return redirect(url_for("billing.pricing"))


@bp.route("/callback")
def callback():
  authority = request.args.get("Authority", "")
  status = request.args.get("Status", "")

  payment = Payment.query.filter_by(authority=authority, status="pending").first()

  if not payment:
    flash("تراکنش یافت نشد.", "error")
    return redirect(url_for("auth.login"))

  user = db.session.get(User, payment.user_id)
  if user and (not current_user.is_authenticated or current_user.id != user.id):
    login_user(user, remember=True)

  if status != "OK":
    payment.status = "failed"
    db.session.commit()
    flash("پرداخت لغو شد یا ناموفق بود.", "error")
    return redirect(url_for("billing.pricing"))

  try:
    result = zarinpal.verify_payment(authority, payment.amount_toman)
    payment.status = "paid"
    payment.ref_id = result["ref_id"]
    payment.verified_at = now_tehran()
    db.session.commit()
    activate_paid_subscription(
      current_user.id, payment.plan_slug, payment.period_months
    )
    flash(f"پرداخت موفق! کد پیگیری: {payment.ref_id}", "success")
    return redirect(url_for("dashboard.dashboard"))
  except Exception as e:
    payment.status = "failed"
    db.session.commit()
    flash(f"تأیید پرداخت ناموفق: {e}", "error")
    return redirect(url_for("billing.pricing"))
