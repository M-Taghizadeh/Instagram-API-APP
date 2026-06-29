import re
import requests

from insta_agent.config import Config

GRAPH_API = Config.GRAPH_API

_MEDIA_FIELDS = (
  "id,shortcode,caption,thumbnail_url,media_url,media_type,permalink,timestamp,"
  "children{thumbnail_url,media_url,media_type}"
)


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


def page_sender_ids(token: str, *known_ids: str) -> set[str]:
  """Instagram professional account IDs that represent our connected page."""
  ids = {str(i) for i in known_ids if i}
  page_id = get_page_ig_id(token)
  if page_id:
    ids.add(str(page_id))
  return ids


def page_sender_ids_for_user(user_id: int, token: str, *known_ids: str) -> set[str]:
  from insta_agent.models import IgAccount

  ids = page_sender_ids(token, *known_ids)
  for acc in IgAccount.query.filter_by(user_id=user_id).all():
    if acc.ig_user_id:
      ids.add(str(acc.ig_user_id))
  return ids


def is_page_sender(sender_id: str, page_ids: set[str]) -> bool:
  return bool(sender_id) and str(sender_id) in page_ids


def should_process_inbound_dm(event: dict, page_ids: set[str]) -> tuple[bool, str]:
  """Only customer messages addressed TO our page should run DM rules/flows."""
  message = event.get("message") or {}
  if message.get("is_echo") or message.get("is_self") or event.get("is_echo"):
    return False, "echo"

  sender_id = str((event.get("sender") or {}).get("id", ""))
  if is_page_sender(sender_id, page_ids):
    return False, "page_sender"

  if page_ids:
    recipient_id = str((event.get("recipient") or {}).get("id", ""))
    if recipient_id and recipient_id not in page_ids:
      return False, "outbound_not_to_page"

  return True, ""


def extract_dm_text(event: dict) -> str:
  message = event.get("message") or {}
  text = (message.get("text") or "").strip()
  if text:
    return text
  qr = message.get("quick_reply") or {}
  if qr:
    return (qr.get("payload") or qr.get("title") or "").strip()
  postback = event.get("postback") or {}
  if postback:
    return (postback.get("payload") or postback.get("title") or "").strip()
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
  image = item.get("thumbnail_url") or item.get("media_url", "")
  if not image and item.get("media_type") == "CAROUSEL_ALBUM":
    children = (item.get("children") or {}).get("data", [])
    if children:
      image = children[0].get("thumbnail_url") or children[0].get("media_url", "")
  return {
    "id": item.get("id", ""),
    "caption": (item.get("caption") or "")[:120],
    "image": image,
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
      params={"fields": _MEDIA_FIELDS, "access_token": access_token},
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
      "fields": _MEDIA_FIELDS,
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
