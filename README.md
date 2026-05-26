# Scalable Notification Gateway

A production-grade, highly resilient notification ingestion and delivery engine built as an advanced distributed systems portfolio project. Engineered with **Clean Architecture**, this platform handles multi-channel delivery (SMS, Email, Push), dynamic user preference routing, guaranteed at-least-once execution via the Transactional Outbox Pattern, Two-Tier Idempotency, and survives catastrophic infrastructure failures through Chaos-tested self-healing mechanisms.

---

## Architecture

> Full architectural blueprint, lifecycle traces, and design justifications: [docs/architecture/README.md](./docs/architecture/README.md)

---

## Features

* **Transactional Outbox Pattern** — guarantees zero data loss if downstream message brokers fail; decouples API ingestion (< 15ms) from network delivery.
* **User Preference & Routing Engine** — millisecond-fast preference filtering (Do-Not-Disturb, channel/template opt-outs) protected by a Redis Cache-Aside pattern with strict write-through invalidation.
* **Time-Travel Protection (Late-Bound Checks)** — prevents state drift for scheduled notifications by re-evaluating user consent at the exact moment of background dispatch, safely suppressing revoked intents.
* **Two-Tier Idempotency Shield** — protects against "thundering herd" duplicate requests using a Redis `SETNX` distributed lock (Tier 1) and PostgreSQL historical unique constraints (Tier 2).
* **PgBouncer Multiplexing** — safely funnels up to 5,000 concurrent API connections through just 80 physical database connections using `poolclass=NullPool`.
* **Linear Horizontal Scaling** — Redpanda (Kafka) partition mapping allows dynamic scaling of isolated channel workers (`sms`, `email`, `push`) without idle starvation.
* **Chaos-Tested Resiliency** — lazy-initialization and client-side reconnection protocols ensure workers survive Redis OOM crashes and IP re-resolutions mid-flight.
* **Observability & Telemetry** — Native Prometheus metric scraping (measuring queue depths, throughput, and worker health), structured JSON logging with request correlation IDs, and an architectural foundation ready for OpenTelemetry distributed tracing.
* **Circuit Breakers & DLQ** — isolated worker failures (e.g., Twilio 503s) route to a Dead Letter Queue after exponential backoff, preventing queue blockage.
* **Clean Architecture** — strict dependency inversion. Domain and Use Cases have zero knowledge of HTTP, SQL, or Kafka.

---

## Scale Targets

| Metric | Local Hardware Baseline | Production Target (Cloud) |
| --- | --- | --- |
| Daily Active Users | N/A | 1,000,000+ |
| Notifications/day | ~12.9 million | 50+ million |
| Peak Throughput | ~150 req/sec | 2,000+ req/sec |
| Ingestion Latency | 6ms - 15ms | < 10ms |
| PgBouncer Capacity | 80 DB Connections | 500 DB Connections |
| Error Rate (API) | 0.00% under heavy load | 99.99% Uptime |

---

## Services & Endpoints

### Core Infrastructure

| Service | Port | Description |
| --- | --- | --- |
| `api` | 8000 | FastAPI — strictly stateless ingestion, idempotency checking, DB insertion. |
| `dispatcher_daemon` | — | Background worker — reads from PostgreSQL Outbox and publishes to Redpanda. |
| `sms_worker` | — | Redpanda consumer → Twilio / Mock Provider. |
| `email_worker` | — | Redpanda consumer → SendGrid / Mock Provider. |
| `push_worker` | — | Redpanda consumer → APNs / FCM. |
| `scheduler_worker` | — | Polls Redis ZSET every 0.5s, routes due messages to the Outbox. |

### API Endpoints
| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/notifications/` | Create and dispatch (or schedule) a notification. Requires `idempotency_key`. |
| `PUT` | `/api/v1/users/{id}/preferences` | Update user opt-outs and DND. Instantly invalidates Redis cache. |
| `GET` | `/health` | Liveness probe for orchestration tools. |
| `GET` | `:9090/metrics` | Prometheus target exposing internal app metrics (Throughput, Latency, Job counts). |

*Interactive API docs available at: `http://localhost:8000/docs*`

---

## Getting Started

### Prerequisites

* Docker & Docker Compose

### Run Locally

```bash
git clone https://github.com/Dosu333/notification_service.git
cd notification_service

# Copy environment variables
cp .env.example .env

# Boot the infrastructure & API
docker-compose up -d --build

```

### Database Migrations

Migrations *must* bypass PgBouncer and run directly against PostgreSQL on port 5432.

```bash
docker-compose run --rm api alembic upgrade head

```

### Scale the Worker Fleet

To achieve maximum parallel throughput, match the worker replicas to your Redpanda topic partition count (e.g., 8 partitions):

```bash
docker-compose up -d --scale sms_worker=8 --scale email_worker=4

```

---

## Key Design Decisions

**Why the Transactional Outbox Pattern?**
Directly calling third-party APIs (Twilio) during an HTTP request ties the system's availability to the provider's availability. The Outbox pattern persists the intent atomically with the database, allowing the API to respond in <15ms while delivery happens asynchronously.

**Why a Two-Tier Idempotency Shield?**
Relying solely on DB `UNIQUE` constraints burns CPU during traffic spikes. We "Fail-Open" a Redis `SETNX` lock (Tier 1) to deflect exact-millisecond "double-clicks" in RAM, and fallback to PostgreSQL (Tier 2) to catch historical duplicate retries.

**Why Redis Cache-Aside for User Preferences?**
Checking user consent on every request at 2,000 RPS would crush PostgreSQL. We cache preferences in Redis with a 5-minute TTL. Crucially, the `PUT /preferences` API performs a strict **cache invalidation** upon updating the database, guaranteeing data consistency without sacrificing read speed.

**Why Late-Bound Checks for Scheduled Tasks?**
If a user schedules a notification for Friday, but opts out on Wednesday, checking preferences only at the time of ingestion creates a "Time-Travel" state drift. The Scheduler worker performs a *Late-Bound Check* microseconds before dispatching to Kafka, ensuring absolute compliance with current user consent.

**Why PgBouncer?**
PostgreSQL assigns one OS process per connection. 2,000 concurrent API users would exhaust DB RAM and cause a crash. PgBouncer multiplexes thousands of lightweight API connections into 80 heavy DB connections, protecting the database during traffic spikes.

---

## What I Learned

* **Distributed State Management:** The complexities of maintaining data consistency between persistent storage (PostgreSQL) and ephemeral caches (Redis) using Cache-Aside and Write-Through invalidation patterns.
* **Atomic Redis Transactions (Lua):** Writing server-side Lua scripts to guarantee thread-safe, atomic operations (like `ZPOPMIN` for scheduled tasks) across concurrent workers without the heavy overhead of distributed locking.
* **Connection Pool Corruptions:** The danger of "Double Pooling" and why SQLAlchemy must use `poolclass=NullPool` when operating behind a transactional proxy like PgBouncer.
- **Distributed Observability:** Why passing a generated `correlation_id` through the API, into the database JSON payload, and across the Kafka wire is strictly necessary to debug missing events in an asynchronous ecosystem.
* **Chaos Engineering:** How to write Bash scripts to `SIGKILL` containers mid-flight to prove that workers drop stale DNS caches and dynamically self-heal IP resolutions.
* **Consumer Group Math:** Why scaling Docker `--scale` beyond Redpanda partition counts results in wasteful, idle containers, and how to orchestrate live rebalances.
* **Tradeoffs:** Choosing to "Fail Open" on distributed Redis locks to prioritize overall system API availability over strict RAM-level deduplication during outages.

---

## Documentation Suite

| Manual | Location | Description |
| --- | --- | --- |
| **System Design Blueprint** | [`docs/architecture/README.md`](./docs/architecture/README.md) | Architectural boundaries, lifecycle traces, and design justifications. |
| **Ingestion Engine Manual** | [`src/apps/api/README.md`](./src/apps/api/README.md) | API contracts, Preference management, and HTTP error matrices. |
| **Processing Fleet Manual** | [`src/apps/workers/README.md`](./src/apps/workers/README.md) | Kafka partition rules, Late-Bound Checks, and DLQ replay steps. |
| **Data Boundaries Manual** | [`src/infrastructure/README.md`](./src/infrastructure/README.md) | PgBouncer multiplexing matrix, Cache Invalidation protocols, and connection invariants. |
| **Chaos & Resiliency Runbook** | [`tools/chaos/README.md`](./tools/chaos/README.md) | Locust load testing targets and Fault Injection (SIGKILL) execution guide. |
| **Troubleshooting & Incident Log** | [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md) | Architectural race conditions, Chaos testing casualties, and root-cause analyses. |
