import datetime
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")


def now_tehran():
  return datetime.datetime.now(TEHRAN).replace(tzinfo=None)
