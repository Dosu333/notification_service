import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker
from src.infrastructure.messaging.kafka_consumer import KafkaMessageConsumer
from src.infrastructure.database.repositories import SqlAlchemyUserPreferenceRepository
from src.use_cases.dispatch_notification import DispatchNotificationUseCase
from src.infrastructure.observability.logger import configure_json_logging


configure_json_logging()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_dispatcher():
    load_dotenv()
    kafka_url = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")
    db_url = os.environ.get("DATABASE_URL")
    group_id = os.environ.get("DISPATCHER_GROUP_ID", "dispatcher-group")
    
    logger.info(f"Starting Dispatcher Daemon connected to {kafka_url}...")

    # Create sessions per message to ensure clean transaction boundaries and avoid long-lived sessions
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Instantiate Brokers
    message_broker = KafkaMessageBroker(bootstrap_servers=kafka_url)
    dlq_broker = KafkaMessageBroker(bootstrap_servers=kafka_url)

    # Message Handler (Session-per-message pattern)
    def handle_message(payload: Dict[str, Any]) -> None:
        # Open a fresh database transaction for this event
        with SessionLocal() as db_session:
            # Instantiate repo with fresh session
            pref_repo = SqlAlchemyUserPreferenceRepository(db_session)
            
            use_case = DispatchNotificationUseCase(
                message_broker=message_broker,
                user_preference_repo=pref_repo
            )

            use_case.execute(payload)

    # Instantiate Consumer
    message_consumer = KafkaMessageConsumer(
        bootstrap_servers=kafka_url, 
        group_id=group_id,
        dlq_broker=dlq_broker,
        dlq_topic="notification.dlq"
    )

    try:
        message_consumer.start_consuming(
            topic="notification.events", 
            handler=handle_message
        )
    except Exception as e:
        logger.critical(f"Dispatcher Daemon encountered a fatal crash: {e}")


if __name__ == "__main__":
    run_dispatcher()
