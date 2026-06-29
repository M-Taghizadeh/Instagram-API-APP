from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from insta_agent.extensions import db
from insta_agent.models import DmRule, CommentRule
from insta_agent.config import Config
from insta_agent.db_init import get_access_token
from insta_agent.services.instagram_api import get_post_preview

bp = Blueprint("rules", __name__)
PER_PAGE = Config.PER_PAGE


def _resolve_post_meta(post_link: str) -> dict:
  """Use preview data submitted with the form, then fall back to Graph API."""
  post_id = request.form.get("post_id", "").strip()
  post_thumb = request.form.get("post_thumb", "").strip()
  post_caption = request.form.get("post_caption", "").strip()
  token = get_access_token(current_user.id)

  if post_link and post_id and post_thumb:
    return {
      "id": post_id,
      "image": post_thumb,
      "caption": post_caption[:120] if post_caption else "",
    }

  preview = get_post_preview(post_link, token, media_id=post_id) if post_link and token else {}
  if preview.get("image"):
    return preview

  if post_id or post_thumb:
    return {
      "id": post_id,
      "image": post_thumb,
      "caption": post_caption[:120] if post_caption else "",
    }
  return preview or {}


# ── DM Rules ──
@bp.route("/dm-rules")
@login_required
def dm_rules():
  q = request.args.get("q", "").strip()
  page = request.args.get("page", 1, type=int)
  query = DmRule.query.filter_by(user_id=current_user.id)
  if q:
    query = query.filter(DmRule.trigger.ilike(f"%{q}%") | DmRule.response.ilike(f"%{q}%"))
  pagination = query.order_by(DmRule.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
  return render_template("dm_rules.html", pagination=pagination, q=q)


@bp.route("/dm-rule/new", methods=["GET", "POST"])
@login_required
def new_dm_rule():
  if request.method == "POST":
    rule = DmRule(
      user_id=current_user.id,
      trigger=request.form.get("trigger", "").strip(),
      response=request.form.get("response", "").strip(),
      match_type=request.form.get("match_type", "contains"),
      is_active=True,
    )
    db.session.add(rule)
    db.session.commit()
    flash("قانون دایرکت ساخته شد.", "success")
    return redirect(url_for("rules.dm_rules"))
  return render_template("dm_rule_form.html", rule=None)


@bp.route("/dm-rule/<rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_dm_rule(rule_id):
  rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  if request.method == "POST":
    rule.trigger = request.form.get("trigger", "").strip()
    rule.response = request.form.get("response", "").strip()
    rule.match_type = request.form.get("match_type", "contains")
    db.session.commit()
    flash("قانون ویرایش شد.", "success")
    return redirect(url_for("rules.dm_rules"))
  return render_template("dm_rule_form.html", rule=rule)


@bp.route("/dm-rule/<rule_id>/toggle", methods=["POST"])
@login_required
def toggle_dm_rule(rule_id):
  rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  rule.is_active = not rule.is_active
  db.session.commit()
  return jsonify(active=rule.is_active)


@bp.route("/dm-rule/<rule_id>/delete", methods=["POST"])
@login_required
def delete_dm_rule(rule_id):
  rule = DmRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  db.session.delete(rule)
  db.session.commit()
  flash("قانون حذف شد.", "success")
  return redirect(url_for("rules.dm_rules"))


# ── Comment Rules ──
@bp.route("/comment-rules")
@login_required
def comment_rules():
  q = request.args.get("q", "").strip()
  page = request.args.get("page", 1, type=int)
  query = CommentRule.query.filter_by(user_id=current_user.id)
  if q:
    query = query.filter(
      CommentRule.trigger.ilike(f"%{q}%") |
      CommentRule.comment_reply.ilike(f"%{q}%") |
      CommentRule.dm_response.ilike(f"%{q}%")
    )
  pagination = query.order_by(CommentRule.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
  return render_template("comment_rules.html", pagination=pagination, q=q)


@bp.route("/comment-rule/new", methods=["GET", "POST"])
@login_required
def new_comment_rule():
  if request.method == "POST":
    post_link = request.form.get("post_link", "").strip()
    meta = _resolve_post_meta(post_link)
    comment_reply = request.form.get("comment_reply", "").strip()
    dm_response = request.form.get("dm_response", "").strip()
    if not comment_reply and not dm_response:
      flash("حداقل یکی از پاسخ کامنت یا دایرکت را وارد کن.", "error")
      return render_template("comment_rule_form.html", rule=None)
    if comment_reply and not dm_response:
      flash("پاسخ دایرکت خالی است — بدون آن پیام خصوصی ارسال نمی‌شود.", "error")
      return render_template("comment_rule_form.html", rule=None)
    rule = CommentRule(
      user_id=current_user.id,
      post_link=post_link,
      post_id=meta.get("id", ""),
      post_caption=meta.get("caption", ""),
      post_thumb=meta.get("image", ""),
      trigger=request.form.get("trigger", "").strip(),
      match_type=request.form.get("match_type", "contains"),
      comment_reply=comment_reply,
      dm_response=dm_response,
      is_active=True,
    )
    db.session.add(rule)
    db.session.commit()
    flash("قانون کامنت ساخته شد.", "success")
    return redirect(url_for("rules.comment_rules"))
  return render_template("comment_rule_form.html", rule=None)


@bp.route("/comment-rule/<rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_comment_rule(rule_id):
  rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  if request.method == "POST":
    post_link = request.form.get("post_link", "").strip()
    meta = _resolve_post_meta(post_link)
    comment_reply = request.form.get("comment_reply", "").strip()
    dm_response = request.form.get("dm_response", "").strip()
    if not comment_reply and not dm_response:
      flash("حداقل یکی از پاسخ کامنت یا دایرکت را وارد کن.", "error")
      return render_template("comment_rule_form.html", rule=rule)
    if comment_reply and not dm_response:
      flash("پاسخ دایرکت خالی است — بدون آن پیام خصوصی ارسال نمی‌شود.", "error")
      return render_template("comment_rule_form.html", rule=rule)
    if post_link != rule.post_link or not rule.post_thumb or meta.get("image"):
      rule.post_id = meta.get("id", rule.post_id or "")
      rule.post_caption = meta.get("caption", rule.post_caption or "")
      if meta.get("image"):
        rule.post_thumb = meta.get("image", "")
    rule.post_link = post_link
    rule.trigger = request.form.get("trigger", "").strip()
    rule.match_type = request.form.get("match_type", "contains")
    rule.comment_reply = comment_reply
    rule.dm_response = dm_response
    db.session.commit()
    flash("قانون ویرایش شد.", "success")
    return redirect(url_for("rules.comment_rules"))
  return render_template("comment_rule_form.html", rule=rule)


@bp.route("/comment-rule/<rule_id>/toggle", methods=["POST"])
@login_required
def toggle_comment_rule(rule_id):
  rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  rule.is_active = not rule.is_active
  db.session.commit()
  return jsonify(active=rule.is_active)


@bp.route("/comment-rule/<rule_id>/delete", methods=["POST"])
@login_required
def delete_comment_rule(rule_id):
  rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  db.session.delete(rule)
  db.session.commit()
  flash("قانون حذف شد.", "success")
  return redirect(url_for("rules.comment_rules"))


@bp.route("/api/post-preview")
@login_required
def api_post_preview():
  link = request.args.get("link", "").strip()
  if not link:
    return jsonify(error="لینک وارد نشده"), 400
  token = get_access_token(current_user.id)
  if not token:
    return jsonify(error="توکن دسترسی تنظیم نشده"), 400
  preview = get_post_preview(link, token)
  if not preview:
    return jsonify(error="پست پیدا نشد"), 404
  return jsonify(preview)


def _apply_preview(rule, preview: dict):
  if not preview:
    return False
  rule.post_id = preview.get("id", rule.post_id or "")
  rule.post_caption = preview.get("caption", rule.post_caption or "")
  rule.post_thumb = preview.get("image", "")
  return bool(rule.post_thumb)


@bp.route("/api/refresh-post-thumbs", methods=["POST"])
@login_required
def api_refresh_post_thumbs():
  token = get_access_token(current_user.id)
  if not token:
    return jsonify(updated=0)
  rules = CommentRule.query.filter_by(user_id=current_user.id).filter(
    or_(
      CommentRule.post_link != "",
      CommentRule.post_id != "",
    )
  ).filter(
    or_(CommentRule.post_thumb == "", CommentRule.post_thumb.is_(None))
  ).all()
  updated = 0
  for rule in rules:
    preview = get_post_preview(rule.post_link or "", token, media_id=rule.post_id or "")
    if _apply_preview(rule, preview):
      updated += 1
  if updated:
    db.session.commit()
  return jsonify(updated=updated)


@bp.route("/api/comment-rule/<rule_id>/refresh-thumb", methods=["POST"])
@login_required
def api_refresh_rule_thumb(rule_id):
  rule = CommentRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
  token = get_access_token(current_user.id)
  if not token:
    return jsonify(error="توکن دسترسی تنظیم نشده"), 400
  if not rule.post_link and not rule.post_id:
    return jsonify(error="پستی برای این قانون ثبت نشده"), 400
  preview = get_post_preview(rule.post_link or "", token, media_id=rule.post_id or "")
  if not preview or not preview.get("image"):
    return jsonify(error="تصویر پست در دسترس نیست"), 404
  _apply_preview(rule, preview)
  db.session.commit()
  return jsonify(image=rule.post_thumb, id=rule.post_id)
