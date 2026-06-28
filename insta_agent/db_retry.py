import time

from sqlalchemy.exc import DBAPIError, OperationalError

from insta_agent.extensions import db

_MAX_RETRIES = 3


def is_disconnect_error(exc: BaseException) -> bool:
  msg = str(exc).lower()
  return any(
    part in msg
    for part in (
      "eof detected",
      "ssl syscall",
      "connection reset",
      "connection refused",
      "server closed",
      "broken pipe",
      "can't connect",
      "connection timed out",
    )
  )


def db_retry(fn, retries: int = _MAX_RETRIES):
  """Run a DB-heavy callable; retry on transient PostgreSQL disconnects."""
  last: BaseException | None = None
  for attempt in range(retries):
    try:
      return fn()
    except (OperationalError, DBAPIError) as exc:
      last = exc
      db.session.rollback()
      db.session.remove()
      if not is_disconnect_error(exc) or attempt >= retries - 1:
        raise
      time.sleep(0.25 * (attempt + 1))
  if last:
    raise last
