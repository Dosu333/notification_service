# API Test Payloads

This document contains standard JSON payloads and `curl` commands for testing the Enterprise Notification Gateway.

**Base URL:** `http://localhost:8000/api/v1`

---

## 1. Standard One-Off Notification (SMS)

A standard, immediate dispatch. Ensure `idempotency_key` is unique per request to bypass the Redis `SETNX` lock.

```bash
curl -X POST http://localhost:8000/api/v1/notifications/ \
-H "Content-Type: application/json" \
-d '{
  "user_id": "usr_123abc",
  "channel": "sms",
  "template": "security_alert",
  "payload": {
    "phone_number": "+2348000000000",
    "message": "Your verification code is 492011."
  },
  "idempotency_key": "idm_auth_9912",
  "scheduled_at": null,
  "recurrence_rule": null,
  "timezone": "UTC"
}'

```

---

## 2. Future-Scheduled Notification (Email)

Tests the Redis ZSET time-travel scheduler. Set `scheduled_at` to a few minutes in the future.

```bash
curl -X POST http://localhost:8000/api/v1/notifications/ \
-H "Content-Type: application/json" \
-d '{
  "user_id": "usr_456def",
  "channel": "email",
  "template": "marketing_promo",
  "payload": {
    "to_email": "testuser@example.com",
    "subject": "Flash Sale Starts Now!",
    "body": "Click here to claim your 50% discount."
  },
  "idempotency_key": "idm_promo_5521",
  "scheduled_at": "2026-05-30T14:00:00Z",
  "recurrence_rule": null,
  "timezone": "UTC"
}'

```

---

## 3. Recurring Notification (The "Spawn-on-Fire" Pattern)

Tests the recurring cron-parser. This schedules a message and includes a `recurrence_rule`. When the worker dispatches this, it will automatically spawn the *next* database row.

```bash
curl -X POST http://localhost:8000/api/v1/notifications/ \
-H "Content-Type: application/json" \
-d '{
  "user_id": "usr_789ghi",
  "channel": "push",
  "template": "daily_reminder",
  "payload": {
    "device_token": "fcm_token_xyz987",
    "title": "Daily Standup",
    "body": "Please submit your daily standup notes."
  },
  "idempotency_key": "idm_standup_base",
  "scheduled_at": "2026-05-27T09:00:00Z",
  "recurrence_rule": "0 9 * * 1-5", 
  "timezone": "UTC"
}'

```

*(Note: `0 9 * * 1-5` means 9:00 AM, Monday through Friday).*

---

## 4. Update User Preferences (PUT)

Tests the Cache-Aside Redis invalidation layer. Updates the user's consent and instantly purges their 5-minute cache.

```bash
curl -X PUT http://localhost:8000/api/v1/users/usr_456def/preferences \
-H "Content-Type: application/json" \
-d '{
  "dnd": false,
  "channels": {
    "SMS": false,
    "EMAIL": true,
    "PUSH": true
  },
  "templates": {
    "marketing_promo": false,
    "security_alert": true
  }
}'

```

---

## 5. Idempotency Collision Test (The Thundering Herd)

To test the Two-Tier Idempotency Shield, run this script. It attempts to fire the exact same request 5 times simultaneously. The API should return `202 ACCEPTED` for the first request, and `200 OK` (with status `ALREADY_PROCESSED`) for the other four.

```bash
#!/bin/bash
for i in {1..5}; do
   curl -s -X POST http://localhost:8000/api/v1/notifications/ \
   -H "Content-Type: application/json" \
   -d '{
     "user_id": "usr_999xyz",
     "channel": "sms",
     "payload": {"phone_number": "+12345678900", "message": "Duplicate test!"},
     "idempotency_key": "idm_collision_test_001"
   }' &
done
wait

```