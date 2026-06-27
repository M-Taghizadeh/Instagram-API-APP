from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user

from insta_agent.extensions import db
from insta_agent.models import SmsConfig, SmsLog, Contact
from insta_agent.services.sms_gateway import send_sms, send_bulk_sms
from insta_agent.services.export import export_phones_excel

bp = Blueprint("sms", __name__, url_prefix="/sms")


@bp.route("")
@login_required
def sms_panel():
  cfg = SmsConfig.query.filter_by(user_id=current_user.id).first()
  logs = SmsLog.query.filter_by(user_id=current_user.id).order_by(SmsLog.created_at.desc()).limit(20).all()
  phone_count = Contact.query.filter_by(user_id=current_user.id).filter(Contact.phone != "").count()
  return render_template("sms.html", cfg=cfg, logs=logs, phone_count=phone_count)


@bp.route("/settings", methods=["POST"])
@login_required
def sms_settings():
  cfg = SmsConfig.query.filter_by(user_id=current_user.id).first()
  if not cfg:
    cfg = SmsConfig(user_id=current_user.id)
    db.session.add(cfg)
  cfg.provider = request.form.get("provider", "kavenegar")
  cfg.api_key = request.form.get("api_key", "").strip()
  cfg.sender = request.form.get("sender", "").strip()
  cfg.is_active = request.form.get("is_active") == "1"
  db.session.commit()
  flash("تنظیمات پیامک ذخیره شد.", "success")
  return redirect(url_for("sms.sms_panel"))


@bp.route("/send", methods=["POST"])
@login_required
def send_single():
  cfg = SmsConfig.query.filter_by(user_id=current_user.id).first()
  if not cfg or not cfg.is_active:
    flash("ابتدا تنظیمات پیامک را فعال کن.", "error")
    return redirect(url_for("sms.sms_panel"))
  phone = request.form.get("phone", "").strip()
  message = request.form.get("message", "").strip()
  if not phone or not message:
    flash("شماره و متن الزامی است.", "error")
    return redirect(url_for("sms.sms_panel"))
  ok = send_sms(current_user.id, cfg.provider, {"api_key": cfg.api_key, "sender": cfg.sender}, phone, message)
  flash("پیامک ارسال شد." if ok else "ارسال ناموفق بود.", "success" if ok else "error")
  return redirect(url_for("sms.sms_panel"))


@bp.route("/bulk", methods=["POST"])
@login_required
def send_bulk():
  cfg = SmsConfig.query.filter_by(user_id=current_user.id).first()
  if not cfg or not cfg.is_active:
    flash("ابتدا تنظیمات پیامک را فعال کن.", "error")
    return redirect(url_for("sms.sms_panel"))
  message = request.form.get("message", "").strip()
  if not message:
    flash("متن پیام الزامی است.", "error")
    return redirect(url_for("sms.sms_panel"))
  contacts = Contact.query.filter_by(user_id=current_user.id).filter(Contact.phone != "").all()
  phones = [c.phone for c in contacts if c.phone]
  result = send_bulk_sms(current_user.id, cfg.provider, {"api_key": cfg.api_key, "sender": cfg.sender}, phones, message)
  flash(f"ارسال انبوه: {result['sent']} موفق، {result['failed']} ناموفق.", "success")
  return redirect(url_for("sms.sms_panel"))


@bp.route("/export-phones")
@login_required
def export_phones():
  contacts = Contact.query.filter_by(user_id=current_user.id).filter(Contact.phone != "").all()
  buf = export_phones_excel(contacts)
  return send_file(buf, as_attachment=True, download_name="sms_phones.xlsx",
                   mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
