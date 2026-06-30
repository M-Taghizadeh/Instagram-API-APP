from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
import json

from insta_agent.extensions import db
from insta_agent.models import Contact
from insta_agent.config import Config
from insta_agent.services.export import export_contacts_excel, export_phones_excel

bp = Blueprint("contacts", __name__, url_prefix="/contacts")
PER_PAGE = Config.PER_PAGE


@bp.route("")
@login_required
def contact_list():
  q = request.args.get("q", "").strip()
  page = request.args.get("page", 1, type=int)
  query = Contact.query.filter_by(user_id=current_user.id)
  if q:
    query = query.filter(
      Contact.ig_username.ilike(f"%{q}%") |
      Contact.phone.ilike(f"%{q}%") |
      Contact.full_name.ilike(f"%{q}%") |
      Contact.email.ilike(f"%{q}%") |
      Contact.custom_fields_json.ilike(f"%{q}%")
    )
  pagination = query.order_by(Contact.updated_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
  # Parse custom fields JSON once in backend so templates don't depend on fromjson filter
  for c in pagination.items:
    try:
      c.custom_fields = json.loads(c.custom_fields_json or "{}")
    except Exception:
      c.custom_fields = {}
  total = Contact.query.filter_by(user_id=current_user.id).count()
  with_phone = Contact.query.filter_by(user_id=current_user.id).filter(Contact.phone != "").count()
  return render_template("contacts.html", pagination=pagination, q=q, total=total, with_phone=with_phone)


@bp.route("/export")
@login_required
def export_contacts():
  contacts = Contact.query.filter_by(user_id=current_user.id).order_by(Contact.created_at.desc()).all()
  buf = export_contacts_excel(contacts)
  return send_file(buf, as_attachment=True, download_name="contacts.xlsx",
                   mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export-phones")
@login_required
def export_phones():
  contacts = Contact.query.filter_by(user_id=current_user.id).filter(Contact.phone != "").all()
  buf = export_phones_excel(contacts)
  return send_file(buf, as_attachment=True, download_name="phones.xlsx",
                   mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/<int:contact_id>/delete", methods=["POST"])
@login_required
def delete_contact(contact_id):
  c = Contact.query.filter_by(id=contact_id, user_id=current_user.id).first_or_404()
  db.session.delete(c)
  db.session.commit()
  flash("مخاطب حذف شد.", "success")
  return redirect(url_for("contacts.contact_list"))
