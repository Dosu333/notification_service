# Troubleshooting Log

A running record of bugs, race conditions, and logical traps hit during the development and load-testing of the Notification Gateway, including root causes and architectural fixes.

---

## 1. Redis DNS Caching — `Temporary failure in name resolution`

**Error**

```text
Error in scheduler loop: Error -3 connecting to redis:6379. Temporary failure in name resolution.

```

**Root cause**
During Chaos Test B, I sent a `SIGKILL` to the Redis container to simulate a crash. When Docker brought a new Redis container back up, it assigned it a new internal IP address. However, the `scheduler_worker` was using a persistent, long-lived `redis.Redis()` client instantiated at startup. The Python process held onto the stale DNS cache of the old IP address, causing an infinite crash loop even after Redis was fully online.

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

This is the perfect addition to your troubleshooting log because it highlights a very common architectural friction point: **Data Transfer Object (DTO) vs. Domain Entity leakage**.

Here is the exact formatted block. Just append this to the very bottom of your `docs/TROUBLESHOOTING.md` file.

```markdown
---

## 6. Redis Serialization Crash — Domain Entity Leakage

**Error**
```text
File "/usr/local/lib/python3.11/json/encoder.py", line 180, in default
    raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
TypeError: Object of type UserPreference is not JSON serializable

```

**Root cause**
After refactoring the User Preference module to adhere strictly to Clean Architecture, the `UserPreferenceRepository` was updated to return a strongly-typed Domain Entity (a Python `dataclass`) instead of a raw dictionary.

However, the Redis Cache-Aside provider (`RedisUserPreferenceProvider`) attempted to push this object directly into Redis RAM using `json.dumps(prefs_dict)`. Because the standard Python JSON library does not know how to serialize custom domain objects, it threw a `TypeError`, causing the API endpoint to crash.

**Fix**
Added an explicit `.to_dict()` serialization method to the `UserPreference` domain entity to safely flatten the object into primitive Python types (booleans, strings, dicts). Updated the Redis provider to call this mapper before caching.

```python
# Before (Crash)
user_pref_entity = self.db_repo.get_by_user_id(user_id)
self.client.setex(name, time, value=json.dumps(user_pref_entity))

# After (Fixed)
user_pref_entity = self.db_repo.get_by_user_id(user_id)
prefs_dict = user_pref_entity.to_dict() # Flatten to primitives
self.client.setex(name, time, value=json.dumps(prefs_dict))

```

**Lesson**
Never allow complex Domain Entities to leak directly into infrastructure serialization boundaries (like Redis, Kafka, or HTTP responses). Always explicitly map entities into primitive Data Transfer Objects (DTOs) or dictionaries before interacting with external stores.

---

## 6. Scheduler Crash — `UniqueViolation` on existing Primary Key

**Error**
```text
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "notifications_pkey"
```

**Root cause**
The Scheduler worker crashed while attempting to update a delayed notification's status from `SCHEDULED` to `QUEUED`. Because the system strictly adheres to Clean Architecture, the Database Repository mapped the SQLAlchemy ORM model into a pure Python dataclass (Domain Entity) before handing it to the Use Case.

When the Use Case handed the modified Domain Entity back to the `UnitOfWork` to save, the infrastructure layer mapped it back into a *new* SQLAlchemy ORM instance and called `session.add()`. SQLAlchemy lost the state tracking, assumed it was a brand-new row, and attempted an `INSERT` rather than an `UPDATE`.

**Fix**
Updated the `UnitOfWork` and Repository layers to use `session.merge(model)` instead of `session.add(model)`. `merge()` forces SQLAlchemy to inspect the Primary Key, match it against the database, and issue a safe `UPDATE` statement, bridging the gap between stateless Domain Entities and stateful ORM tracking.
