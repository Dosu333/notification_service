import time
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from src.infrastructure.database.models import OutboxEventModel
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker


load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")
KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_publisher():
    broker = KafkaMessageBroker(bootstrap_servers=KAFKA_BROKER_URL)
    print("Starting Outbox Publisher Daemon...")
    
    while True:
        with SessionLocal() as session:
            try:
                # Fetch unhandled events in batches of 50
                events = session.query(OutboxEventModel)\
                    .filter(OutboxEventModel.processed == 0)\
                    .order_by(OutboxEventModel.created_at.asc())\
                    .limit(50)\
                    .with_for_update(skip_locked=True)\
                    .all()

                if not events:
                    # If the outbox is empty, sleep
                    time.sleep(1) 
                    continue

                for event in events:
                    # Publish event to the appropriate Kafka topic
                    broker.publish(topic=event.topic, payload=event.payload)
                    
                    # Update the state in the database model
                    event.processed = 1
                    event.processed_at = datetime.utcnow()

                # Flush the broker to guarantee messages actually reached the broker
                broker.flush()
                
                # Commit the database transaction. 
                session.commit()
                print(f"Successfully published and committed {len(events)} events.")

            except Exception as e:
                session.rollback()
                print(f"Error processing outbox events: {e}")
                time.sleep(5)  # Sleep before retrying


if __name__ == "__main__":
    run_publisher()