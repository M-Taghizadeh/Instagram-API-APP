import re
import requests

from insta_agent.config import Config


def get_triggers(trigger_str: str) -> list:
  parts = re.split(r"[،,\n]+", trigger_str or "")
  return [p.strip() for p in parts if p.strip()]


def match_text(trigger_str: str, text: str, match_type: str = "contains") -> bool:
  if not text:
    return False
  text = text.lower().strip()
  for trigger in get_triggers(trigger_str):
    t = trigger.lower()
    if match_type == "exact":
      if t == text:
        return True
    else:
      if t in text:
        return True
  return False
