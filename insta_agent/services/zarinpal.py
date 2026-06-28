import requests

from insta_agent.services.app_settings_service import (
  zarinpal_merchant_id,
  zarinpal_sandbox_mode,
  zarinpal_is_configured,
)


def _base_urls():
  if zarinpal_sandbox_mode():
    return (
      "https://sandbox.zarinpal.com/pg/v4/payment",
      "https://sandbox.zarinpal.com/pg/StartPay/",
    )
  return (
    "https://api.zarinpal.com/pg/v4/payment",
    "https://www.zarinpal.com/pg/StartPay/",
  )


def is_configured() -> bool:
  return zarinpal_is_configured()


def request_payment(amount_toman: int, callback_url: str, description: str) -> dict:
  merchant = zarinpal_merchant_id()
  if not merchant:
    raise ValueError("Merchant ID زرین‌پال تنظیم نشده")
  base, start = _base_urls()
  amount_rial = amount_toman * 10
  r = requests.post(
    f"{base}/request.json",
    json={
      "merchant_id": merchant,
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
  return {"authority": authority, "url": f"{start}{authority}"}


def verify_payment(authority: str, amount_toman: int) -> dict:
  merchant = zarinpal_merchant_id()
  base, _ = _base_urls()
  amount_rial = amount_toman * 10
  r = requests.post(
    f"{base}/verify.json",
    json={
      "merchant_id": merchant,
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
