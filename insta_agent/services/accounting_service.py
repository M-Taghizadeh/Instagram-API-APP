import csv
import datetime
import io
from collections import defaultdict

from insta_agent.extensions import db
from insta_agent.models import Payment
from insta_agent.utils import now_tehran, parse_jalali_date, format_jalali, jalali_month_bounds, now_jalali

PERIOD_LABELS = {
  "today": "امروز",
  "month": "این ماه",
  "year": "امسال",
  "custom": "بازه دلخواه",
  "month_pick": "ماه انتخابی",
  "all": "کل دوره",
}

MONTH_NAMES = [
  "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def parse_date(s: str) -> datetime.datetime | None:
  j = parse_jalali_date(s)
  if j:
    return j.replace(hour=0, minute=0, second=0, microsecond=0)
  if not s:
    return None
  try:
    d = datetime.datetime.strptime(s[:10], "%Y-%m-%d")
    return d.replace(hour=0, minute=0, second=0, microsecond=0)
  except ValueError:
    return None


def resolve_range(period: str, date_from: str = "", date_to: str = "",
                  year: int | None = None, month: int | None = None) -> tuple:
  now = now_tehran()
  end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

  if period == "today":
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    label = f"امروز ({format_jalali(now)})"
  elif period == "month":
    jnow = now_jalali()
    start, end = jalali_month_bounds(jnow.year, jnow.month)
    if end > now:
      end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    label = f"ماه جاری ({MONTH_NAMES[jnow.month]} {jnow.year})"
    year = jnow.year
    month = jnow.month
  elif period == "year":
    jy = year or now_jalali().year
    start, _ = jalali_month_bounds(jy, 1)
    _, end = jalali_month_bounds(jy, 12)
    if end > now:
      end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    label = f"سال {jy}"
    year = jy
    month = now_jalali().month
  elif period == "month_pick" and year and month:
    start, end = jalali_month_bounds(year, month)
    if end > now:
      end = now.replace(hour=23, minute=59, second=59)
    mn = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
    label = f"{mn} {year}"
  elif period == "custom":
    start = parse_date(date_from) or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_d = parse_date(date_to) or now
    end = end_d.replace(hour=23, minute=59, second=59, microsecond=999999)
    label = f"{format_jalali(start)} — {format_jalali(end_d)}"
  else:
    start = datetime.datetime(2000, 1, 1)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    period = "all"
    label = "کل دوره"

  if not year:
    year = now_jalali().year
  if not month:
    month = now_jalali().month
  return start, end, period, label, year, month


def _in_range(dt, start, end):
  if not dt:
    return False
  return start <= dt <= end


def build_report(period: str, date_from: str = "", date_to: str = "",
                 year: int | None = None, month: int | None = None,
                 status_filter: str = "") -> dict:
  start, end, period, period_label, year, month = resolve_range(
    period, date_from, date_to, year, month
  )
  now = now_tehran()

  all_payments = Payment.query.order_by(Payment.created_at.desc()).all()

  in_range = []
  for p in all_payments:
    ref_dt = p.verified_at if p.status == "paid" and p.verified_at else p.created_at
    if _in_range(ref_dt, start, end):
      if status_filter and p.status != status_filter:
        continue
      in_range.append(p)

  paid = [p for p in in_range if p.status == "paid"]
  failed = [p for p in in_range if p.status == "failed"]
  pending = [p for p in in_range if p.status == "pending"]

  revenue = sum(p.amount_toman for p in paid)
  count_paid = len(paid)
  avg = revenue // count_paid if count_paid else 0

  revenue_all = sum(
    p.amount_toman for p in all_payments if p.status == "paid"
  )

  by_plan = defaultdict(lambda: {"count": 0, "revenue": 0})
  for p in paid:
    by_plan[p.plan_slug]["count"] += 1
    by_plan[p.plan_slug]["revenue"] += p.amount_toman
  plan_rows = sorted(by_plan.items(), key=lambda x: -x[1]["revenue"])

  by_period = defaultdict(lambda: {"count": 0, "revenue": 0})
  for p in paid:
    key = f"{p.period_months} ماهه"
    by_period[key]["count"] += 1
    by_period[key]["revenue"] += p.amount_toman
  period_rows = sorted(by_period.items(), key=lambda x: -x[1]["revenue"])

  daily = defaultdict(int)
  for p in paid:
    dt = p.verified_at or p.created_at
    if dt:
      daily[dt.strftime("%Y-%m-%d")] += p.amount_toman
  daily_sorted = sorted(daily.items())
  chart_labels = [d[5:].replace("-", "/") for d, _ in daily_sorted]
  chart_data = [v for _, v in daily_sorted]

  monthly_rows = []
  for m in range(1, 13):
    m_start, m_end = jalali_month_bounds(year, m)
    rev = 0
    for p in all_payments:
      if p.status != "paid":
        continue
      dt = p.verified_at or p.created_at
      if dt and m_start <= dt <= m_end:
        rev += p.amount_toman
    monthly_rows.append({
      "month": m,
      "name": MONTH_NAMES[m],
      "revenue": rev,
    })

  return {
    "period": period,
    "period_label": period_label,
    "start": start,
    "end": end,
    "revenue": revenue,
    "revenue_all": revenue_all,
    "count_paid": count_paid,
    "count_failed": len(failed),
    "count_pending": len(pending),
    "avg_transaction": avg,
    "payments": in_range,
    "plan_rows": plan_rows,
    "period_rows": period_rows,
    "chart_labels": chart_labels,
    "chart_data": chart_data,
    "monthly_rows": monthly_rows,
    "year": year,
    "month": month,
    "date_from": date_from,
    "date_to": date_to,
    "status_filter": status_filter,
  }


def export_csv(report: dict) -> str:
  buf = io.StringIO()
  w = csv.writer(buf)
  w.writerow(["id", "user", "plan", "period_months", "amount_toman", "status", "ref_id", "verified_at"])
  for p in report["payments"]:
    w.writerow([
      p.id,
      p.user.username if p.user else p.user_id,
      p.plan_slug,
      p.period_months,
      p.amount_toman,
      p.status,
      p.ref_id,
      (p.verified_at or p.created_at).strftime("%Y-%m-%d %H:%M") if (p.verified_at or p.created_at) else "",
    ])
  return buf.getvalue()
