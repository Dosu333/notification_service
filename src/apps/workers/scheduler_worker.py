import os
import time
import logging
import uuid
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.database.models import NotificationModel, OutboxEventModel
from src.infrastructure.observability.logger import configure_json_logging, set_correlation_id
from src.infrastructure.redis.queue import RedisSchedulerQueue


configure_json_logging()
logger = logging.getLogger(__name__)


def run_scheduler():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    queue = RedisSchedulerQueue(redis_url)

    logger.info("Starting Scheduler Daemon connected to RedisQueue...")

    while True:
        try:
            current_time = time.time()
            notification_id_str = queue.pop_due_item(current_time)

            if not notification_id_str:
                time.sleep(0.5)
                continue

            notification_id = uuid.UUID(notification_id_str)
            set_correlation_id(f"sched-{notification_id}")
            
            with SessionLocal() as session:
                notification = session.query(NotificationModel).filter_by(id=notification_id).first()
                
                if not notification or notification.status != "SCHEDULED":
                    continue

                outbox_payload = {
                    "notification_id": str(notification.id),
                    "user_id": notification.user_id,
                    "channel": notification.channel,
                    "template": notification.template,
                    "payload": notification.payload,
                    "correlation_id": f"sched-{notification.id}"
                }

                outbox_event = OutboxEventModel(
                    topic="notification.events",
                    payload=outbox_payload,
                    processed=0
                )
                
                notification.status = "PENDING"

                session.add(outbox_event)
                session.commit()
                
                logger.info(f"Bridged scheduled notification {notification.id} to the Outbox.")

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_scheduler()
