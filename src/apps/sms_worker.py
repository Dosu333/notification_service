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
from src.infrastructure.providers.twilio_sms_provider import TwilioSMSProvider
from src.use_cases.send_channel_notification import SendChannelNotificationUseCase


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_sms_worker():
    load_dotenv()
    kafka_url = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")
    db_url = os.environ.get("DATABASE_URL")
    
    # Setup Database Engine
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Setup Infrastructure Dependencies
    dlq_broker = KafkaMessageBroker(bootstrap_servers=kafka_url)
    sms_provider = TwilioSMSProvider(
        account_sid=os.environ.get("TWILIO_ACCOUNT_SID", "mock"),
        auth_token=os.environ.get("TWILIO_AUTH_TOKEN", "mock"),
        from_number=os.environ.get("TWILIO_FROM_NUMBER", "mock")
    )
    
    # Message handler that will be called for each consumed message
    def handle_message(payload: Dict[str, Any]) -> None:
        notification_id = uuid.UUID(payload["notification_id"])
        
        # Open fresh DB transaction for this message
        with SessionLocal() as db_session:
            repo = SqlAlchemyNotificationRepository(db_session)
            
            # Inject SMS provider
            use_case = SendChannelNotificationUseCase(
                notification_repo=repo,
                sms_provider=sms_provider
            )
            
            # Execute business logic
            use_case.execute(notification_id)
            
            # Commit the status update to database
            db_session.commit()

    consumer = KafkaMessageConsumer(
        bootstrap_servers=kafka_url,
        group_id="sms-workers",
        dlq_broker=dlq_broker,
        dlq_topic="notification.dlq"
    )
    
    logger.info("Starting SMS Worker Daemon...")
    consumer.start_consuming(topic="sms.queue", handler=handle_message)


if __name__ == "__main__":
    run_sms_worker()