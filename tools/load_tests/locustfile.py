import random
import uuid
from datetime import datetime, timedelta
from locust import HttpUser, task, between


class NotificationUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def _generate_payload(self):
        """Helper to generate a random but valid notification payload."""
        channels = ["sms", "email", "push"]
        
        base_request = {
            "user_id": f"usr_{random.randint(1000, 99999)}",
            "channel": random.choice(channels),
            "payload": {
                "message": "This is a load-test notification.",
                "event_id": str(uuid.uuid4())
            },
            "idempotency_key": f"idm_{uuid.uuid4()}",
            "template": "system_alert"
        }
        return base_request

    @task(7) # 70% probability weighting
    def send_immediate_notification(self):
        """Tests the Postgres Outbox saturation."""
        request_data = self._generate_payload()
        
        with self.client.post("/api/v1/notifications/", json=request_data, catch_response=True) as response:
            if response.status_code in [200, 202]:
                response.success()
            else:
                response.failure(f"Immediate Failed: {response.status_code}")

    @task(3) # 30% probability weighting
    def send_scheduled_notification(self):
        """Tests the Redis ZADD latency and Timezone logic."""
        request_data = self._generate_payload()
        
        # Randomize a time between 1 day and 30 days in the future
        future_time = datetime.utcnow() + timedelta(days=random.randint(1, 30), minutes=random.randint(1, 60))
        request_data["scheduled_at"] = future_time.isoformat() + "Z"
        
        # 50% chance of the scheduled notification being a recurring one
        if random.choice([True, False]):
            cron_options = ["0 8 * * *", "0 12 * * 4", "30 9 1 * *"]
            request_data["recurrence_rule"] = random.choice(cron_options)
            request_data["timezone"] = random.choice(["UTC", "Africa/Lagos", "Europe/Berlin"])

        with self.client.post("/api/v1/notifications/", json=request_data, catch_response=True) as response:
            if response.status_code in [200, 202]:
                response.success()
            else:
                response.failure(f"Scheduled Failed: {response.status_code}")
