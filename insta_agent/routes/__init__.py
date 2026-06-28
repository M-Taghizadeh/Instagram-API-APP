from insta_agent.routes import (
  main, auth, oauth, dashboard, webhook, rules,
  settings_routes, activity, flows, contacts, followup, sms_routes, media_routes,
  billing, admin,
)

ALL_BLUEPRINTS = [
  main.bp,
  auth.bp,
  oauth.bp,
  dashboard.bp,
  webhook.bp,
  rules.bp,
  settings_routes.bp,
  activity.bp,
  flows.bp,
  contacts.bp,
  followup.bp,
  sms_routes.bp,
  media_routes.bp,
  billing.bp,
  admin.bp,
]
