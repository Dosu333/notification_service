# Data Boundaries & Connection

## 📖 Overview

This directory contains the implementations for the **Infrastructure Layer** of the Clean Architecture.

This layer dictates how the system safely connects to the outside world. This manual outlines the rules, network invariants, and configuration protocols required to maintain database stability under extreme concurrency.

Failure to adhere to these configuration rules will result in corrupted prepared statements or deadlocks.

---

## 🚦 1. PgBouncer Multiplexing Matrix

PostgreSQL uses a process-per-connection model. Spawning thousands of native Postgres connections to handle API traffic spikes will exhaust the database's RAM and cause an outage. To prevent this, all application traffic routes through **PgBouncer**, a lightweight connection pooler.

### Configuration Constants

Operate PgBouncer in **Transaction Mode**.

* **`POOL_MODE=transaction`**: A server connection is assigned to a client (FastAPI/Worker) only for the duration of a single database transaction. The microsecond the `COMMIT` or `ROLLBACK` is issued, the connection is returned to the pool. This allows thousands of concurrent clients to share a tiny pool of actual database connections.
* **`DEFAULT_POOL_SIZE=80`**: Native Postgres defaults to 100 `max_connections`. I allocated 80  to PgBouncer for application traffic. The remaining 20 are reserved as a buffer for direct admin queries, monitoring tools, and CI/CD database migrations.
* **`MAX_CLIENT_CONN=5000`**: PgBouncer will accept up to 5,000 incoming TCP connections from the scaling Python workers. It will hold them in lightweight RAM queues and funnel them through the 80 heavy Postgres connections.

### Connection Routing Matrix

| Actor | Target Port | Protocol | Pool Usage | Max Capacity |
| --- | --- | --- | --- | --- |
| **FastAPI / Uvicorn** | `6432` (PgBouncer) | Multiplexed | High | 5,000 active sockets |
| **Python Workers** | `6432` (PgBouncer) | Multiplexed | High | 5,000 active sockets |
| **Alembic Migrations** | `5432` (Direct Postgres) | Dedicated | Low | Buffer (20 slots) |
| **Data/Admin Ops** | `5432` (Direct Postgres) | Dedicated | Low | Buffer (20 slots) |

---


## 🛣️ 2. Alembic Direct Route Exception

Alembic executes DDL (Data Definition Language)—creating tables, dropping columns, and altering schema structures.
PgBouncer's `transaction` mode strips session-level state. Because migrations often require complex, multi-step session locks and rely on persistent `search_path` variables to execute safely, running them through a multiplexer can lead to partial migrations and corrupted schema states.

### Execution Protocol

When writing deployment scripts or CI/CD pipelines, make sure `MIGRATION_DATABASE_URL` is set to inject the direct PostgreSQL URI, bypassing port `6432` and targeting port `5432`.

**In `alembic.ini` or `.env`:**

```ini
# ❌ WRONG: Do not run migrations through PgBouncer
# MIGRATION_DATABASE_URL=postgresql://user:password@localhost:6432/notifdb

# ✅ CORRECT: Direct access using the reserved 20-connection buffer
MIGRATION_DATABASE_URL=postgresql://user:password@localhost:5432/notifdb

```

**Execution Command:**

```bash
docker-compose run --rm -e DATABASE_URL=$MIGRATION_DATABASE_URL api alembic upgrade head

```

## 🧠 3. Redis Cache-Aside & Invalidation
User preferences are read on every API notification request and every Scheduler dispatch. To protect PostgreSQL from being crushed under 2,000+ reads per second, Redis Cache-Aside pattern is used.

### The Read Path (Fail-Safe)
1. The `RedisUserPreferenceProvider` attempts to read `prefs:{user_id}` from RAM.
2. On a cache miss, it queries PostgreSQL, then writes the result to Redis with a **300-second (5-minute) TTL**.
3. **Resiliency:** If Redis is offline, the provider catches the `ConnectionError`, logs a warning, and routes all traffic directly to PostgreSQL, allowing the system to degrade gracefully.

### The Write Path (Invalidation)
Any update to the PostgreSQL preference table is immediately followed by `redis.delete(f"prefs:{user_id}")`. Failing to invalidate the cache will result in the system dispatching unwanted messages to users for up to 5 minutes based on stale RAM data.