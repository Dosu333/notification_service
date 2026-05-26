# Scalable Notification Gateway


## 🚀 Project Summary

This repository contains the core ingestion and delivery engine for our high-throughput, asynchronous messaging platform.

Engineered adhering to **Clean Architecture**, this system is designed to process thousands of requests per second (RPS) and scale to support millions of active users. It decouples the immediate intent to send a message from the actual network delivery, utilizing the **Transactional Outbox Pattern** to ensure zero data loss during upstream provider outages (e.g., Twilio, SendGrid, APNs).

**Core Capabilities:**

* **Asynchronous Dispatch:** API ingestion completes in < 15ms. Delivery is handled seamlessly in the background.
* **Two-Tier Idempotency:** Distributed Redis locks and database constraints eliminate duplicate processing during heavy network retries.
* **Time-Travel Scheduling:** Redis-backed delayed execution for future marketing or reminder campaigns.
* **Self-Healing Infrastructure:** Workers automatically survive and recover from network drops, broker rebalances, and database restarts.

---

## 🛠️ Technical Stack

The infrastructure is containerized and optimized for high concurrency.

| Component | Technology | Purpose |
| --- | --- | --- |
| **Language** | Python 3.11+ | Core application logic and typing. |
| **API Framework** | FastAPI | High-speed, stateless, async HTTP ingestion. |
| **Message Broker** | Redpanda | Kafka-compatible streaming platform for worker queues. |
| **Primary Database** | PostgreSQL 15+ | Persistent truth, Outbox storage, and historic idempotency. |
| **Connection Pooler** | PgBouncer | Multiplexes 5,000+ API connections into 80 physical database connections. |
| **State / Caching** | Redis | Ephemeral state, distributed locks (`SETNX`), and scheduled task indexing. |
| **Containerization** | Docker / Compose | Local topology orchestration and environment parity. |

---

## ⚡ Getting Started

To get the entire distributed ecosystem running on your local machine, ensure you have Docker and Docker Compose installed, then follow these steps:

**1. Clone and Configure**

```bash
git clone git@github.com:Dosu333/notification_service.git
cd notification-gateway

# Copy the sample environment file (contains safe local defaults)
cp .env.example .env

```

**2. Boot the Infrastructure & Ingestion API**
Bring up the databases, brokers, and the FastAPI application in detached mode:

```bash
docker-compose up -d --build

```

**3. Run Database Migrations**
*Important: Migrations must run directly against Postgres, bypassing PgBouncer.*

```bash
docker-compose run --rm api alembic upgrade head

```

**4. Deploy the Worker Fleet (With Scale)**
Spin up the background consumers. To ensure high throughput and prevent Redpanda partition starvation, scale the workers dynamically:

```bash
docker-compose up -d --scale sms_worker=8 --scale email_worker=4

```

**Access Points:**

* **API Swagger Docs:** `http://localhost:8000/docs`
* **Prometheus Metrics:** `http://localhost:9090`
* **Redpanda CLI:** `docker exec -it redpanda rpk cluster info`

---

## 🗺️ Repository Map (Clean Architecture)

This codebase relies on dependency inversion. Dependencies point *inward* toward the Domain.

```text
.
├── docs/                           # Extended architectural and system documentation
├── tools/                          # QA, Load Testing (Locust), and Chaos Engineering scripts
├── src/
│   ├── domain/                     # 1. CORE: Entities, Enums, and custom Exceptions. Zero external dependencies.
│   ├── use_cases/                  # 2. APPLICATION: Business logic orchestration (e.g., CreateNotification).
│   ├── interfaces/                 # 3. PORTS: Abstract Base Classes for Repositories and Providers.
│   ├── infrastructure/             # 4. ADAPTERS: SQLAlchemy, Redis-py, Kafka producers, PgBouncer rules.
│   └── apps/                       # 5. DELIVERY: The executable processes.
│       ├── api/                    # ↳ FastAPI Routers and Dependency Injection config.
│       └── workers/                # ↳ Kafka Consumer Daemons and Polling loops.
├── docker-compose.yml              # Local infrastructure topology
└── alembic/                        # Database schema migrations

```

---

## 📚 Documentation

This README covers the basic setup. To understand how to extend, deploy, or debug the platform, refer to the localized documentation manuals:

1. **[The System Design Blueprint](./docs/architecture/README.md)** - Visual diagrams, lifecycle traces, and design justifications.
2. **[The Ingestion Engine Manual](./src/apps/api/README.md)** - API payloads, idempotency protocols, and HTTP error matrices.
3. **[The Asynchronous Processing Fleet](./src/apps/workers/README.md)** - Redpanda partition rules, Consumer Groups, and Dead Letter Queue (DLQ) replay steps.
4. **[Data Boundaries & Connection Manual](./src/infrastructure/README.md)** - Rules for PgBouncer multiplexing and SQLAlchemy NullPooling.
5. **[Resiliency & Load Testing Runbook](./tools/chaos/README.md)** - Instructions for Locust swarms and running the Chaos Injection suite.