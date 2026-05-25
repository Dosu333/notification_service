import os
import uuid
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.messaging.kafka_consumer import KafkaMessageConsumer
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker
from src.infrastructure.database.repositories import SqlAlchemyNotificationRepository
from src.infrastructure.providers.firebase_push_provider import FirebasePushProvider
from src.use_cases.send_channel_notification import SendChannelNotificationUseCase
from src.infrastructure.observability.logger import configure_json_logging


configure_json_logging()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_push_worker():
    load_dotenv()
    kafka_url = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")
    db_url = os.environ.get("DATABASE_URL")
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    dlq_broker = KafkaMessageBroker(bootstrap_servers=kafka_url)
    
    # Initialize Firebase Push Provider with service account credentials
    service_account_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "firebase-service-account.json")
    push_provider = FirebasePushProvider(service_account_path=service_account_path)

    def handle_message(payload: Dict[str, Any]) -> None:
        notification_id = uuid.UUID(payload["notification_id"])
        
        with SessionLocal() as db_session:
            repo = SqlAlchemyNotificationRepository(db_session)
            
            use_case = SendChannelNotificationUseCase(
                notification_repo=repo,
                push_provider=push_provider
            )
            
            use_case.execute(notification_id)
            db_session.commit()

    consumer = KafkaMessageConsumer(
        bootstrap_servers=kafka_url,
        group_id="push-workers",
        dlq_broker=dlq_broker,
        dlq_topic="notification.dlq"
    )
    
    logger.info("Starting Push Worker Daemon ...")
    consumer.start_consuming(topic="push.queue", handler=handle_message)


if __name__ == "__main__":
    run_push_worker()