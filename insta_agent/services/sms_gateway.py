import json
import requests

from insta_agent.extensions import db
from insta_agent.models import SmsLog


def send_sms_kavenegar(api_key: str, sender: str, receptor: str, message: str) -> tuple[bool, str]:
  if not api_key:
    return False, "API key not set"
  try:
    url = f"https://api.kavenegar.com/v1/{api_key}/sms/send.json"
    r = requests.post(url, data={
      "receptor": receptor,
      "sender": sender or "",
      "message": message,
    }, timeout=15)
    data = r.json()
    ok = r.status_code == 200 and data.get("return", {}).get("status") == 200
    return ok, json.dumps(data, ensure_ascii=False)[:500]
  except Exception as e:
    return False, str(e)


def send_sms_melipayamak(username: str, password: str, to: str, text: str) -> tuple[bool, str]:
  try:
    r = requests.post("https://rest.payamak-panel.com/api/SendSMS/SendSMS", json={
      "username": username,
      "password": password,
      "to": to,
      "text": text,
    }, timeout=15)
    data = r.json()
    ok = str(data.get("RetStatus")) == "1"
    return ok, json.dumps(data, ensure_ascii=False)[:500]
  except Exception as e:
    return False, str(e)


def send_sms(user_id: int, provider: str, config: dict, phone: str, message: str) -> bool:
  ok, resp = False, ""
  if provider == "kavenegar":
    ok, resp = send_sms_kavenegar(config.get("api_key", ""), config.get("sender", ""), phone, message)
  elif provider == "melipayamak":
    ok, resp = send_sms_melipayamak(
      config.get("api_key", ""), config.get("sender", ""), phone, message
    )
  log = SmsLog(user_id=user_id, phone=phone, message=message,
               status="sent" if ok else "failed", provider_response=resp)
  db.session.add(log)
  db.session.commit()
  return ok


def send_bulk_sms(user_id: int, provider: str, config: dict, phones: list, message: str) -> dict:
  sent, failed = 0, 0
  for phone in phones:
    if send_sms(user_id, provider, config, phone, message):
      sent += 1
    else:
      failed += 1
  return {"sent": sent, "failed": failed}
