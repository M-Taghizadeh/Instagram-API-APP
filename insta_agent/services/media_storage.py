"""Uploaded flow media — track usage and delete orphans."""

import json
import os
import re

from flask import current_app
from werkzeug.utils import secure_filename

from insta_agent.config import Config
from insta_agent.models import Flow

_MEDIA_PATH_RE = re.compile(r"/media/files/([^/?#]+)")


def filename_from_url(url: str) -> str | None:
  if not url:
    return None
  m = _MEDIA_PATH_RE.search(url)
  if not m:
    return None
  return secure_filename(m.group(1)) or None


def normalize_public_media_url(url: str) -> str:
  """Ensure Instagram can fetch the asset via HTTPS."""
  u = (url or "").strip()
  if not u:
    return ""
  if u.startswith("/"):
    base = (Config.PUBLIC_BASE_URL or "").rstrip("/")
    if base:
      u = f"{base}{u}"
  if u.startswith("http://"):
    u = "https://" + u[7:]
  return u


def collect_filenames_from_nodes(nodes: list) -> set[str]:
  names: set[str] = set()
  if not nodes:
    return names
  for node in nodes:
    data = node.get("data") or {}
    fn = filename_from_url(data.get("url", ""))
    if fn:
      names.add(fn)
    for el in data.get("elements") or []:
      fn = filename_from_url(el.get("image_url", ""))
      if fn:
        names.add(fn)
  return names


def collect_filenames_from_flows(user_id: int, exclude_flow_id: str | None = None) -> set[str]:
  names: set[str] = set()
  q = Flow.query.filter_by(user_id=user_id)
  if exclude_flow_id:
    q = q.filter(Flow.id != exclude_flow_id)
  for flow in q.all():
    try:
      nodes = json.loads(flow.nodes_json or "[]")
    except json.JSONDecodeError:
      continue
    names |= collect_filenames_from_nodes(nodes)
  return names


def _upload_dir() -> str:
  try:
    return current_app.config.get("UPLOAD_DIR") or Config.UPLOAD_DIR
  except RuntimeError:
    return Config.UPLOAD_DIR


def delete_files(filenames: set[str]) -> int:
  removed = 0
  base = _upload_dir()
  for name in filenames:
    if not name:
      continue
    path = os.path.join(base, name)
    if os.path.isfile(path):
      try:
        os.remove(path)
        removed += 1
      except OSError:
        pass
  return removed


def cleanup_after_flow_save(user_id: int, old_nodes: list, new_nodes: list, flow_id: str | None = None):
  """Delete files removed from this flow and not used elsewhere."""
  old_names = collect_filenames_from_nodes(old_nodes)
  new_names = collect_filenames_from_nodes(new_nodes)
  still_used = collect_filenames_from_flows(user_id, exclude_flow_id=flow_id)
  still_used |= new_names
  orphans = old_names - still_used
  delete_files(orphans)


def cleanup_flow_media(user_id: int, nodes: list):
  """Delete media files from a flow if no other flow references them."""
  names = collect_filenames_from_nodes(nodes)
  still_used = collect_filenames_from_flows(user_id)
  delete_files(names - still_used)
