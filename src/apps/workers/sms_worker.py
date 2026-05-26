import os
import uuid
import time
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from prometheus_client import start_http_server
from src.infrastructure.messaging.kafka_consumer import KafkaMessageConsumer
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker
from src.infrastructure.database.repositories import SqlAlchemyNotificationRepository
from src.infrastructure.providers.twilio_sms_provider import TwilioSMSProvider
from src.infrastructure.providers.mock_provider import MockSMSProvider
from src.use_cases.send_channel_notification import SendChannelNotificationUseCase
from src.infrastructure.observability.logger import configure_json_logging
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService


configure_json_logging()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_sms_provider():
    """
    Factory method to get the appropriate SMS provider based on environment configuration.
    """
    if os.environ.get("USE_MOCK_PROVIDERS") == "true":
        return MockSMSProvider(provider_name="mock_sms_gateway")
    return TwilioSMSProvider(
            account_sid=os.environ.get("TWILIO_ACCOUNT_SID", "mock"),
            auth_token=os.environ.get("TWILIO_AUTH_TOKEN", "mock"),
            from_number=os.environ.get("TWILIO_FROM_NUMBER", "mock")
        )


def run_sms_worker():
    start_http_server(8002)
    logger.info("Started Prometheus metrics server on port 8002")

    load_dotenv()
    kafka_url = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")
    db_url = os.environ.get("DATABASE_URL")
    
    # Setup Database Engine
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Setup Infrastructure Dependencies
    dlq_broker = KafkaMessageBroker(bootstrap_servers=kafka_url)
    sms_provider = get_sms_provider()
    
    # Instantiate metrics service
    metrics_service = PrometheusMetricsService()
    
    # Message handler that will be called for each consumed message
    def handle_message(payload: Dict[str, Any]) -> None:
        start_time = time.perf_counter()
        status = "success"
        
        try:
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
                
        except Exception as e:
            status = "failed"
            raise e

        finally:
            duration = time.perf_counter() - start_time
            
            metrics_service.increment_counter(
                metric_name="notifications_processed_total", 
                tags={"channel": "sms", "status": status}
            )
            metrics_service.record_histogram(
                metric_name="worker_processing_duration_seconds", 
                value=duration, 
                tags={"channel": "sms"}
            )

    consumer = KafkaMessageConsumer(
        bootstrap_servers=kafka_url,
        group_id="sms-workers",
        dlq_broker=dlq_broker,
        dlq_topic="notification.dlq",
        metrics_service=metrics_service
    )
    
    logger.info("Starting SMS Worker Daemon...")
    consumer.start_consuming(topic="sms.queue", handler=handle_message)


if __name__ == "__main__":
    run_sms_worker()