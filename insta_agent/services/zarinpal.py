import requests

from insta_agent.config import Config

_BASE = "https://sandbox.zarinpal.com/pg/v4/payment" if Config.ZARINPAL_SANDBOX else "https://api.zarinpal.com/pg/v4/payment"
_START = "https://sandbox.zarinpal.com/pg/StartPay/" if Config.ZARINPAL_SANDBOX else "https://www.zarinpal.com/pg/StartPay/"


def is_configured() -> bool:
  return bool(Config.ZARINPAL_MERCHANT_ID)


def request_payment(amount_toman: int, callback_url: str, description: str) -> dict:
  if not is_configured():
    raise ValueError("ZARINPAL_MERCHANT_ID تنظیم نشده")
  amount_rial = amount_toman * 10
  r = requests.post(
    f"{_BASE}/request.json",
    json={
      "merchant_id": Config.ZARINPAL_MERCHANT_ID,
      "amount": amount_rial,
      "callback_url": callback_url,
      "description": description[:255],
    },
    timeout=20,
  )
  data = r.json()
  inner = data.get("data") or {}
  if inner.get("code") != 100:
    errs = data.get("errors") or inner
    raise ValueError(str(errs))
  authority = inner.get("authority", "")
  return {"authority": authority, "url": f"{_START}{authority}"}


def verify_payment(authority: str, amount_toman: int) -> dict:
  amount_rial = amount_toman * 10
  r = requests.post(
    f"{_BASE}/verify.json",
    json={
      "merchant_id": Config.ZARINPAL_MERCHANT_ID,
      "amount": amount_rial,
      "authority": authority,
    },
    timeout=20,
  )
  data = r.json()
  inner = data.get("data") or {}
  code = inner.get("code")
  if code not in (100, 101):
    errs = data.get("errors") or inner
    raise ValueError(str(errs))
  return {"ref_id": str(inner.get("ref_id", "")), "code": code}
