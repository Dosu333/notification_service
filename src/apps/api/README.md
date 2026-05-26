# The Ingestion Engine

## 📖 Overview

This directory contains the Presentation Layer of the system—the FastAPI web server.

The API acts as an **Ingestion Engine**. It is completely stateless and performs zero synchronous network I/O to third-party providers. Its sole responsibility is to validate incoming HTTP requests, enforce idempotency, safely persist the intent to Postgres (or Redis for scheduled tasks), and return a `200 OK` as fast as physically possible (target: < 15ms).

---

## 📝 1. API Contracts

All client integrations must conform to these payload structures. The core ingestion endpoint is `POST /api/v1/notifications/`.

### Scenario A: Instant Dispatch (The Outbox Path)

Used for transactional alerts (e.g., OTPs, Password Resets) that must be sent immediately. The API writes these directly to the database and the Outbox table in a single atomic transaction.

**Request Body:**

```json
{
  "user_id": "usr_987654321",
  "channel": "SMS",
  "template": "security_alert",
  "payload": {
    "ip_address": "192.168.1.1",
    "browser": "Chrome/Mac"
  },
  "idempotency_key": "sec_alert_usr987_1716738"
}

```

### Scenario B: Scheduled Dispatch (The Redis Path)

Used for marketing campaigns, reminders, or future events. If `scheduled_at` is provided, the Outbox is bypassed entirely. The API saves the record to Postgres as `status="SCHEDULED"` and pushes the pointer into the Redis Sorted Set for the `scheduler_worker` to process later.

**Request Body:**

```json
{
  "user_id": "usr_123456789",
  "channel": "EMAIL",
  "template": "subscription_renewal",
  "payload": {
    "first_name": "Alice",
    "renewal_date": "2026-06-01"
  },
  "idempotency_key": "sub_renew_usr123_2026",
  "scheduled_at": "2026-05-30T09:00:00Z",
  "timezone": "UTC"
}

```

---

## 🛡️ 2. The Two-Tier Idempotency Shield

Network volatility means mobile clients will frequently retry HTTP requests if they experience a timeout. To prevent sending duplicate text messages (and paying double Twilio fees), the API enforces a strict Two-Tier Idempotency strategy.

All clients **must** provide a unique `idempotency_key` (UUID v4 or deterministic hash) with every request.

### Tier 1: The Redis Gatekeeper (Race Condition Protection)

* **The Mechanism:** When a request hits the endpoint, the API immediately calls `SETNX idempotency:lock:<key>` in Redis.
* **The Goal:** Deflect exact-same-millisecond "double-clicks". Redis is single-threaded and operates in RAM. It allows the first request through and rejects simultaneous duplicates in < 1ms, saving the database from connection exhaustion or heavy constraint-checking.
* **Resiliency:** If Redis is down, this layer "Fails Open" to prevent an API outage, relying entirely on Tier 2.

### Tier 2: The Postgres Vault (Historical Protection)

* **The Mechanism:** After passing Redis, the API queries Postgres (`get_by_idempotency_key`).
* **The Goal:** Deflect historical duplicates. Since Redis locks expire (usually after 24 hours to save RAM), a client retrying a request 3 days later will bypass Tier 1. Postgres maintains the permanent `UNIQUE` constraint and historical record to catch these late retries.

*If either tier detects a duplicate, the system halts processing and returns a simulated success response (see Error Matrix below).*

---

## 🚥 3. Error Response Matrix

In accordance with Clean Architecture, the API layer (`routers`) never contains business logic. Instead, it executes Use Cases and catches specific Domain Exceptions, translating them into standard HTTP status codes.

Here is the translation matrix frontend clients and API gateways should expect:

| Domain Exception | HTTP Status | Response Body | Client Action Required |
| --- | --- | --- | --- |
| **None (Success)** | `200 OK` | `{"success": true, "notification_id": "..."}` | Proceed. |
| **IdempotencyConflictException** | `200 OK` | `{"success": true, "status": "ALREADY_PROCESSED"}` | **None.** Treat as success. The system safely ignored the duplicate. |
| **ValidationException** | `422 Unprocessable` | `{"success": false, "error": "Invalid channel type."}` | **Fix Code.** The payload violates domain rules. Do not retry without modifying. |
| **RateLimitExceededException** | `429 Too Many Requests` | `{"success": false, "error": "User quota exceeded."}` | **Backoff.** The user has received too many messages in a short window. |
| **DatabaseConnectionError** | `500 Server Error` | `{"success": false, "error": "Internal infrastructure error."}` | **Retry.** PgBouncer or Postgres is temporarily overloaded. Clients should apply exponential backoff. |

### Note on 200 OK for Conflicts

`IdempotencyConflictException` results in a `200 OK`

This is an intentional design choice. If a client is retrying a request because it dropped the original response packet, telling the client "Error: You already did this" forces the client to write complex error-handling logic. By returning a `200 OK (ALREADY_PROCESSED)`, the client seamlessly assumes its retry succeeded and clears its local queue.

## ⚙️ 4. Preference Management Contracts
The API provides endpoints to manage user consent, routing, and Do-Not-Disturb (DND) windows.

### Update Preferences (`PUT /api/v1/users/{user_id}/preferences`)
Updates the database and instantly triggers a Redis Cache Invalidation (`redis.delete()`) to prevent stale reads.

**Request Body:**
```json
{
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
}

