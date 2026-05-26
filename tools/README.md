# Resiliency & Load Testing


## 📖 Overview

This document details how to validate the platform's behavior under extreme concurrency and how to intentionally induce catastrophic infrastructure failures to prove its self-healing mechanisms operate as designed.

The core philosophy: **Everything fails. The system must survive.**

---

## 🚦 Part 1: Locust Swarm Guide (Load Testing)

Utilize [Locust](https://locust.io/) to simulate sudden "thundering herd" traffic spikes. The goal is to saturate the ingestion path (FastAPI ➡️ PgBouncer ➡️ Postgres) and observe the backpressure mechanics.

### 1. Prerequisites

Ensure the full stack is running with a scaled worker fleet to handle the processing load:

```bash
docker-compose up -d --build --scale sms_worker=8

```

### 2. Executing the Swarm

Navigate to the `tools/load_tests` directory and run Locust in headless mode for a clean terminal output, or via the UI for graphs:

**Headless (Automated CI/CD validation):**

```bash
locust -f locustfile.py --headless -u 2000 -r 200 --run-time 5m --host http://localhost:8000

```

*(This spawns 2,000 concurrent users at a rate of 200 users per second, running for 5 minutes).*

### 3. Baseline SRE Benchmarks

Based on local hardware validation, a successful stress test must align with these benchmarks. In cloud environments, RPS will scale linearly with CPU allocation.

| Metric | Local Benchmark | Production SLA | Failure Threshold |
| --- | --- | --- | --- |
| **Total Requests** | ~40,000 - 62,000 | N/A | N/A |
| **Peak Throughput** | ~150 RPS | 2,000+ RPS | Drops below 100 RPS |
| **Min Ingestion Latency** | ~15ms | < 10ms | > 50ms |
| **Error Rate (500s)** | **0.00%** | **< 0.01%** | **> 0.00% under normal load** |
| **PgBouncer Pool Utilization** | 80 Connections | 500 Connections | Exhaustion (Connection Refused) |

*Note: The ~15ms minimum latency accounts for the local Docker bridged network proxying through PgBouncer.*

---

## 🔥 Part 2: Chaos Suite Execution (Fault Injection)

Chaos engineering proves the system is resilient. Execute these three specific scenarios to sever infrastructure components mid-flight.

Run the interactive Chaos CLI from the root directory:

```bash
./tools/chaos/inject_faults.sh [test-a | test-b | test-c]

```

### Test A: The Outbox Drop (Broker Disconnect)

**Objective:** Prove the API remains highly available even if the asynchronous message broker pipeline is completely offline.

* **Action:** The script sends a `SIGSTOP` to the `outbox_publisher` container during peak Locust traffic.
* **Expected System Behavior:** * The API continues to return `200 OK`.
* Locust reports 0% failures.
* Postgres `outbox_events` table grows rapidly as messages queue safely on disk.


* **Validation:** Upon restoring the publisher, verify via the Redpanda console that the publisher bulk-flushes the Postgres backlog into the Kafka topics without dropping a single event.

### Test B: Redis Volatility (State Crash & Re-resolution)

**Objective:** Prove the system recovers from ephemeral IP address changes and state-store crashes without requiring manual worker restarts.

* **Action:** The script executes a hard `kill` on the Redis container, simulating an Out-of-Memory (OOM) crash, and boots a blank instance on a new internal Docker IP.
* **Expected System Behavior:**
* **API Layer (Idempotency):** Detects the connection drop and "Fails Open," allowing requests through to Postgres to handle unique constraint validation.
* **Worker Layer (Scheduler):** Throws `redis.ConnectionError` and drops the stale DNS cache.


* **Validation:** Look at the `scheduler_worker` logs. Within 5 seconds, the `_ensure_connected()` lazy-initialization loop must automatically resolve the new Redis IP and log `"Successfully connected to Redis"` without the Python process ever exiting.

### Test C: Upstream Provider 503 (Third-Party Outage)

**Objective:** Prove the worker circuit breaker isolates failing external APIs (e.g., Twilio, SendGrid) to prevent queue blockage.

* **Action:** Injects the `CHAOS_MODE="503"` environment variable into a new mock worker, forcing the provider adapter to throw HTTP 503 Service Unavailable errors.
* **Expected System Behavior:**
* The specific worker halts processing for that channel.
* Messages exceeding the retry threshold are stripped from the main topic and routed to the `dlq.notifications` (Dead Letter Queue) topic.


* **Validation:** Verify the worker process remains alive (does not crash loop). Inspect the Redpanda DLQ topic to ensure the failed payloads are safely stored for manual replay.

---

## ⏱️ Part 3: Self-Healing & Topology Benchmarks

When monitoring Grafana / Prometheus during incident recovery, expect the following automated recovery timelines based on the architectural design:

1. **Kafka Partition Rebalance Delay (~10 to 15 seconds):**
* *Trigger:* Adding or removing `sms_worker` containers.
* *Behavior:* Redpanda executes a "Stop-The-World" rebalance. Processing will temporarily flatline to 0 RPS across all workers.
* *Resolution:* After exactly 10-15 seconds, partition ownership is reassigned, and processing resumes dynamically. **Do not manually restart workers during this window.**


2. **PgBouncer Connection Saturation Recovery (< 2 seconds):**
* *Trigger:* Traffic spikes exceeding the `DEFAULT_POOL_SIZE`
* *Behavior:* New API requests are queued in PgBouncer's RAM rather than failing. Latency spikes slightly (queue delay).
* *Resolution:* As transactions commit (usually in < 5ms), queued connections are immediately serviced. No database memory swapping will occur.


3. **Disaster Recovery Bootstrapper (On Startup):**
* *Trigger:* Full cluster power loss / Redis wipe.
* *Behavior:* The `scheduler_worker` invokes the `BootstrapSchedulerUseCase` on boot.
* *Resolution:* It queries Postgres for all `status="SCHEDULED"` events and reconstructs the Redis Sorted Set in memory before the main daemon loop starts. Expect a startup delay of ~2 seconds per 10,000 scheduled records.