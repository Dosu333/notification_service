#  Asynchronous Processing Fleet


## 📖 Overview

This directory contains the execution environments for the background processing daemons.

While the API (`src/apps/api`) is synchronous, stateless, and optimized for sub-10ms response times, the Workers are asynchronous, stateful, and built for heavy lifting. They are the engine of the Delivery Path, responsible for draining the message brokers, executing third-party network calls, and handling remote provider failures.

---

## 🚢 1. Fleet Profiles & Responsibilities

The worker architecture is deeply segmented. It does not use monolithic workers that process all types of events; instead, specialized fleets to ensure that an outage or rate-limit in one provider (e.g., Apple Push) does not stall the delivery of another (e.g., Twilio SMS).

| Fleet Identity | Consumer Group ID | Source Topic | Primary Responsibility |
| --- | --- | --- | --- |
| **Dispatcher Daemon** | `dispatcher-daemon` | DB Outbox Table | Reads raw events from Postgres and routes them to the correct Kafka/Redpanda channel topics. It is the bridge between Storage and Streaming. |
| **SMS Workers** | `sms-workers` | `sms.queue` | Consumes SMS payloads, interacts with the Twilio/Mock adapter, and handles carrier rate limits. |
| **Email Workers** | `email-workers` | `email.queue` | Consumes Email payloads, renders HTML templates, and interacts with SendGrid/Mock. |
| **Push Workers** | `push-workers` | `push.queue` | Consumes Push payloads, manages device token validation, and interacts with APNs/FCM. |
| **Scheduler Worker** | *(Redis ZSET Poller)* | Redis `delayed_notifications` | Wakes up every 0.5s, checks Redis for timestamps that are `<= current_time`, and routes due messages to the Outbox. |

---

## 🛑 2. Redpanda Partition Mapping

The streaming architecture relies on the **Consumer Group Protocol**. The rule of this protocol is: **A single partition can only be actively consumed by ONE worker within a group at any given time.**

### How Scaling Works

If `sms.queue` topic has **8 partitions**, here is how the cluster behaves based on the Docker replica count:

* **4 Workers (`--scale sms_worker=4`):** Healthy. Each worker is assigned 2 partitions.
* **8 Workers (`--scale sms_worker=8`):** Optimal. 1-to-1 mapping. Maximum parallel throughput.
* **10 Workers (`--scale sms_worker=10`):** **WASTEFUL.** 8 workers will get 1 partition each. **2 workers will sit 100% idle**, burning CPU and RAM for no reason.

### Operations Protocol for Scaling Up

If there is Consumer Lag building up and there is need to scale the SMS fleet to 16 workers,  the topic partitions must be increased *before* or *during* the scale-up event.

**Step 1: Check Current Partitions**

```bash
docker exec -it redpanda rpk topic describe sms_notifications

```

**Step 2: Increase Partitions (e.g., to 16)**

```bash
docker exec -it redpanda rpk topic add-partitions sms_notifications -n 16

```

**Step 3: Scale the Compute**

```bash
docker-compose up -d --scale sms_worker=16

```

*Note: Redpanda will automatically trigger a "Rebalance" (taking ~10 seconds) to map the new 16 partitions to the 16 containers. Containers should not be manually restarted during this window.*

---

## 🚑 3. Dead Letter Queue (DLQ)

When a third-party provider (e.g., Twilio) goes offline and returns HTTP 503 errors, the workers utilize an Exponential Backoff strategy. However, to prevent "Poison Pills" from blocking the entire queue forever, any message that fails 5 consecutive times is stripped from the main topic and pushed to the Dead Letter Queue.

### 3.1. Inspecting the DLQ

```bash
# Peek at the last 10 failed messages
docker exec -it redpanda rpk topic consume dlq.notifications -n 10

```