import json
import threading
import time

from insta_agent.extensions import db
from insta_agent.models import ScheduledMessage, Settings
from insta_agent.services import messaging
from insta_agent.services.subscription_service import expire_due_subscriptions
from insta_agent.utils import now_tehran

_scheduler_started = False


def process_pending_messages(app):
  with app.app_context():
    try:
      expired = expire_due_subscriptions()
      if expired:
        print(f"[SCHEDULER] expired {expired} subscription(s)", flush=True)
    except Exception as e:
      print(f"[SCHEDULER] expire ERROR: {e}", flush=True)

    due = ScheduledMessage.query.filter(
      ScheduledMessage.status == "pending",
      ScheduledMessage.send_at <= now_tehran(),
    ).limit(50).all()

    for job in due:
      from insta_agent.services.subscription_service import has_automation_access
      if not has_automation_access(job.user_id):
        continue
      s = Settings.query.filter_by(user_id=job.user_id).first()
      token = (s.access_token if s else "") or ""
      if not token:
        job.status = "failed"
        job.note = "no token"
        db.session.commit()
        continue
      try:
        payload = json.loads(job.payload_json or "{}")
        ok = messaging.send_payload(job.ig_user_id, payload, token)
        job.status = "sent" if ok else "failed"
        job.sent_at = now_tehran()
        job.note = "ok" if ok else "send failed"
      except Exception as e:
        job.status = "failed"
        job.note = str(e)[:200]
      db.session.commit()


def start_scheduler(app):
  global _scheduler_started
  if _scheduler_started:
    return
  _scheduler_started = True
  interval = app.config.get("SCHEDULER_INTERVAL_SEC", 30)

  def loop():
    while True:
      try:
        process_pending_messages(app)
      except Exception as e:
        print(f"[SCHEDULER] ERROR: {e}", flush=True)
      time.sleep(interval)

  t = threading.Thread(target=loop, daemon=True, name="followup-scheduler")
  t.start()
  print(f"[SCHEDULER] started (every {interval}s)", flush=True)
