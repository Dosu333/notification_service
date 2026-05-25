import time
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from src.infrastructure.database.models import OutboxEventModel
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker
from src.infrastructure.observability.logger import configure_json_logging, set_correlation_id


configure_json_logging()
logger = logging.getLogger(__name__)

load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")
KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_publisher():
    broker = KafkaMessageBroker(bootstrap_servers=KAFKA_BROKER_URL)
    logger.info("Starting Outbox Publisher Daemon...")
    
    while True:
        with SessionLocal() as session:
            try:
                events = session.query(OutboxEventModel)\
                    .filter(OutboxEventModel.processed == 0)\
                    .order_by(OutboxEventModel.created_at.asc())\
                    .limit(50)\
                    .with_for_update(skip_locked=True)\
                    .all()

                if not events:
                    time.sleep(1) 
                    continue

                for event in events:
                    correlation_id = event.payload.get("correlation_id", f"outbox-{event.id}")
                    set_correlation_id(correlation_id)
                    
                    broker.publish(topic=event.topic, payload=event.payload)
                    
                    event.processed = 1
                    event.processed_at = datetime.utcnow()

                broker.flush()
                session.commit()

                logger.info(f"Successfully published and committed {len(events)} events.")

            except Exception as e:
                session.rollback()
                logger.error(f"Error processing outbox events: {e}")
                time.sleep(5)


if __name__ == "__main__":
    run_publisher()