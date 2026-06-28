import datetime
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN = ZoneInfo("Asia/Tehran")

JALALI_MONTH_NAMES = [
  "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def now_tehran():
  return datetime.datetime.now(TEHRAN).replace(tzinfo=None)


def now_jalali() -> jdatetime.datetime:
  return jdatetime.datetime.fromgregorian(datetime=now_tehran())


def parse_jalali_date(s: str) -> datetime.datetime | None:
  if not s:
    return None
  s = s.strip().replace("-", "/")
  try:
    parts = [int(p) for p in s.split("/")]
    if len(parts) != 3:
      return None
    g = jdatetime.date(parts[0], parts[1], parts[2]).togregorian()
    return datetime.datetime(g.year, g.month, g.day)
  except (ValueError, TypeError, jdatetime.JalaliDateOutOfRange):
    return None


def format_jalali(dt, fmt: str = "%Y/%m/%d") -> str:
  if not dt:
    return ""
  try:
    if isinstance(dt, datetime.datetime):
      d = dt.date()
    elif isinstance(dt, datetime.date):
      d = dt
    else:
      return ""
    j = jdatetime.date.fromgregorian(date=d)
    return j.strftime(fmt)
  except Exception:
    return ""


def jalali_years(count: int = 6) -> list[int]:
  jy = now_jalali().year
  return list(range(jy, jy - count, -1))


def jalali_month_bounds(jy: int, jm: int) -> tuple[datetime.datetime, datetime.datetime]:
  start_j = jdatetime.date(jy, jm, 1)
  if jm == 12:
    next_j = jdatetime.date(jy + 1, 1, 1)
  else:
    next_j = jdatetime.date(jy, jm + 1, 1)
  g_start = start_j.togregorian()
  g_end = (next_j - datetime.timedelta(days=1)).togregorian()
  start = datetime.datetime(g_start.year, g_start.month, g_start.day, 0, 0, 0)
  end = datetime.datetime(g_end.year, g_end.month, g_end.day, 23, 59, 59)
  return start, end


def add_jalali_months(dt: datetime.datetime, months: int) -> datetime.datetime:
  j = jdatetime.date.fromgregorian(date=dt.date())
  total = j.year * 12 + (j.month - 1) + months
  ny, nm0 = divmod(total, 12)
  nm = nm0 + 1
  for day in range(j.day, 0, -1):
    try:
      g = jdatetime.date(ny, nm, day).togregorian()
      return datetime.datetime(g.year, g.month, g.day, dt.hour, dt.minute, dt.second)
    except jdatetime.JalaliDateOutOfRange:
      continue
  g = jdatetime.date(ny, nm, 1).togregorian()
  return datetime.datetime(g.year, g.month, g.day, dt.hour, dt.minute, dt.second)
