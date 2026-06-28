import re
import requests

from insta_agent.config import Config

GRAPH_API = Config.GRAPH_API


def get_ig_username(ig_user_id: str, access_token: str) -> str:
  if not ig_user_id or not access_token:
    return ""
  try:
    r = requests.get(
      f"{GRAPH_API}/me/conversations",
      headers={"Authorization": f"Bearer {access_token}"},
      params={"fields": "participants", "user_id": ig_user_id, "platform": "instagram"},
      timeout=8,
    )
    for conv in r.json().get("data", []):
      for p in conv.get("participants", {}).get("data", []):
        if p.get("id") == ig_user_id:
          return p.get("username", "")
  except Exception as e:
    print(f"[USERNAME] ERROR: {e}", flush=True)
  return ""


def get_page_ig_id(token: str) -> str:
  try:
    r = requests.get(
      f"{GRAPH_API}/me",
      headers={"Authorization": f"Bearer {token}"},
      params={"fields": "id"},
      timeout=8,
    )
    return r.json().get("id", "")
  except Exception:
    return ""


def resolve_post_id(post_link: str, access_token: str) -> str:
  try:
    m = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", post_link or "")
    if not m or not access_token:
      return ""
    shortcode = m.group(1)
    url = f"{GRAPH_API}/me/media"
    params = {"fields": "id,shortcode", "access_token": access_token, "limit": 100}
    while url:
      resp = requests.get(url, params=params, timeout=10)
      data = resp.json()
      for item in data.get("data", []):
        if item.get("shortcode") == shortcode:
          return item["id"]
      url = (data.get("paging") or {}).get("next")
      params = {}
    return ""
  except Exception as e:
    print("RESOLVE POST ID ERROR:", e)
    return ""


def _media_item_to_preview(item: dict) -> dict:
  return {
    "id": item.get("id", ""),
    "caption": (item.get("caption") or "")[:120],
    "image": item.get("thumbnail_url") or item.get("media_url", ""),
    "type": item.get("media_type", ""),
    "permalink": item.get("permalink", ""),
    "timestamp": item.get("timestamp", ""),
  }


def get_media_by_id(media_id: str, access_token: str) -> dict:
  if not media_id or not access_token:
    return {}
  try:
    resp = requests.get(
      f"{GRAPH_API}/{media_id}",
      params={
        "fields": "id,shortcode,caption,thumbnail_url,media_url,media_type,permalink,timestamp",
        "access_token": access_token,
      },
      timeout=10,
    )
    data = resp.json()
    if data.get("error") or not data.get("id"):
      return {}
    return _media_item_to_preview(data)
  except Exception as e:
    print("GET MEDIA BY ID ERROR:", e)
    return {}


def get_post_preview(post_link: str, access_token: str, media_id: str = "") -> dict:
  if media_id:
    preview = get_media_by_id(media_id, access_token)
    if preview:
      return preview

  try:
    m = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", post_link or "")
    if not m or not access_token:
      return {}
    shortcode = m.group(1)
    url = f"{GRAPH_API}/me/media"
    params = {
      "fields": "id,shortcode,caption,thumbnail_url,media_url,media_type,permalink,timestamp",
      "access_token": access_token,
      "limit": 100,
    }
    while url:
      resp = requests.get(url, params=params, timeout=10)
      data = resp.json()
      if data.get("error"):
        break
      for item in data.get("data", []):
        if item.get("shortcode") == shortcode:
          return _media_item_to_preview(item)
      url = (data.get("paging") or {}).get("next")
      params = {}
    return {}
  except Exception as e:
    print("GET POST PREVIEW ERROR:", e)
    return {}
