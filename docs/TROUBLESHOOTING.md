# Troubleshooting Log

A running record of bugs, race conditions, and logical traps hit during the development and load-testing of the Notification Gateway, including root causes and architectural fixes.

---

## 1. Redis DNS Caching — `Temporary failure in name resolution`

**Error**

```text
Error in scheduler loop: Error -3 connecting to redis:6379. Temporary failure in name resolution.

```

**Root cause**
During Chaos Test B, we sent a `SIGKILL` to the Redis container to simulate a crash. When Docker brought a new Redis container back up, it assigned it a new internal IP address. However, our `scheduler_worker` was using a persistent, long-lived `redis.Redis()` client instantiated at startup. The Python process held onto the stale DNS cache of the old IP address, causing an infinite crash loop even after Redis was fully online.

**Fix**
Moved away from static instantiation to a **Lazy-Initialization** pattern in `RedisSchedulerQueue` and all Redis Providers:

```python
def _ensure_connected(self):
    if self.client is None:
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
        except redis.ConnectionError:
            self.client = None # Force re-resolve on next loop

```

By setting `self.client = None` on exception, the next loop iteration is forced to call `redis.from_url` again, which successfully queries the Docker DNS for the *new* IP address.

---

## 2. Alembic Migration Desync — `relation "notifications" does not exist`

**Error**

```text
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "notifications" does not exist

```

**Root cause**
The worker threw this error despite Alembic migrations showing as "successfully applied." The root cause was a split-brain connection path. The worker was connecting to the database through the PgBouncer multiplexer (port `6432`), while Alembic was configured to hit PostgreSQL directly (port `5432`). PgBouncer's connection parameters were pointing to the `public` schema, but Alembic had executed the table creation in a different schema/database context.

**Fix**
Forced the SQLAlchemy worker engines to explicitly target the `public` schema when routing through PgBouncer:

```python
engine = create_engine(
    DATABASE_URL, 
    poolclass=NullPool,
    connect_args={"options": "-csearch_path=public"}
)

```

**Lesson**
Migrations must always bypass PgBouncer, but the application must explicitly define its `search_path` when connecting through a transaction-mode proxy to ensure it finds the tables Alembic created.

---

## 3. Worker Startup Crash — Race Condition with Infrastructure

**Error**

```text
redis.exceptions.ConnectionError: Error 111 connecting to redis:6379. Connection refused.

```

**Root cause**
The Python workers (`scheduler_worker`, `sms_worker`) were booting up in milliseconds, faster than the Redis and PgBouncer containers could initialize their TCP sockets. The workers attempted to connect, failed, and crashed with `SystemExit`.

**Fix**
Added Docker `healthcheck` configurations to the infrastructure services, and forced the workers to wait for them.

```yaml
# In docker-compose.yml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 5

scheduler_worker:
  depends_on:
    redis:
      condition: service_healthy

```

---

## 4. SQLAlchemy Double Pooling — Prepared Statement Corruption

**Error**

```text
sqlalchemy.exc.InternalError: (psycopg2.errors.DuplicatePstatement) prepared statement "a1b2c3d4" already exists

```

**Root cause**
SQLAlchemy maintains an internal `QueuePool` by default. PgBouncer maintains its own connection pool. This resulted in "Double Pooling". SQLAlchemy would create a prepared statement on a connection and hold the connection open. PgBouncer would multiplex that same underlying database connection to a different worker thread, which would try to create the same prepared statement, causing a collision.

**Fix**
Explicitly disabled SQLAlchemy's internal pooling mechanism so it drops the connection state after every single transaction, yielding control entirely to PgBouncer.

```python
# Before
engine = create_engine(DATABASE_URL)

# After
from sqlalchemy.pool import NullPool
engine = create_engine(DATABASE_URL, poolclass=NullPool)

```

---

## 5. Python Tuple Bug — `AttributeError` on Use Case Execution

**Error**

```text
AttributeError: 'tuple' object has no attribute 'schedule'

```

**Root cause**
A stray trailing comma in the `__init__` method of the `CreateNotificationUseCase` silently converted the `scheduler` dependency into a Python tuple.

```python
# Broken
self.scheduler = scheduler,

# When called later:
self.scheduler.schedule(str(notification.id), unix_timestamp) # CRASH

```

**Fix**
Removed the trailing comma.

**Lesson**
Python's syntax allows implicit tuple creation simply by adding a comma. Always double-check trailing commas in class constructors and dependency injection chains.
