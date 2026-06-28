import os
import uuid

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import login_required
from werkzeug.utils import secure_filename

bp = Blueprint("media", __name__, url_prefix="/media")

ALLOWED = {
  "image": {"png", "jpg", "jpeg", "gif", "webp"},
  "video": {"mp4", "mov", "webm", "avi"},
  "audio": {"mp3", "wav", "m4a", "aac", "ogg"},
}


def _ext_ok(filename, group):
  ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
  return ext in ALLOWED.get(group, set())


@bp.route("/upload", methods=["POST"])
@login_required
def upload():
  f = request.files.get("file")
  media_type = request.form.get("type", "image")
  if not f:
    return jsonify(error="فایلی انتخاب نشده"), 400
  if not _ext_ok(f.filename, media_type):
    return jsonify(error="فرمت فایل مجاز نیست"), 400

  max_bytes = current_app.config.get("MAX_UPLOAD_MB", 50) * 1024 * 1024
  f.seek(0, os.SEEK_END)
  size = f.tell()
  f.seek(0)
  if size > max_bytes:
    return jsonify(error=f"حجم فایل بیش از {current_app.config.get('MAX_UPLOAD_MB', 50)} مگابایت است"), 400

  upload_dir = current_app.config["UPLOAD_DIR"]
  os.makedirs(upload_dir, exist_ok=True)
  ext = secure_filename(f.filename).rsplit(".", 1)[-1].lower()
  name = f"{uuid.uuid4().hex}.{ext}"
  path = os.path.join(upload_dir, name)
  f.save(path)

  base = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
  if base:
    url = f"{base}/media/files/{name}"
  else:
    url = request.url_root.rstrip("/") + f"/media/files/{name}"
  return jsonify(url=url, filename=name, type=media_type)


@bp.route("/files/<filename>")
def serve_file(filename):
  upload_dir = current_app.config["UPLOAD_DIR"]
  return send_from_directory(upload_dir, secure_filename(filename))
