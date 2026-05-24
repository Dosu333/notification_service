import os
import logging
from dotenv import load_dotenv
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker
from src.infrastructure.messaging.kafka_consumer import KafkaMessageConsumer
from src.use_cases.dispatch_notification import DispatchNotificationUseCase


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_dispatcher():
    load_dotenv()
    kafka_url = os.environ.get("KAFKA_BROKER_URL", "localhost:19092")
    group_id = os.environ.get("DISPATCHER_GROUP_ID", "dispatcher-group")
    
    logger.info(f"Starting Dispatcher Daemon connected to {kafka_url}...")

    # Instantiate Message Broker 
    message_broker = KafkaMessageBroker(bootstrap_servers=kafka_url)

    # Instantiate the Use Case with the broker dependency
    use_case = DispatchNotificationUseCase(message_broker=message_broker)

    # Instantiate Consumer
    message_consumer = KafkaMessageConsumer(
        bootstrap_servers=kafka_url, 
        group_id=group_id
    )

    try:
        message_consumer.start_consuming(
            topic="notification.events", 
            handler=use_case.execute
        )
    except Exception as e:
        logger.critical(f"Dispatcher Daemon encountered a fatal crash: {e}")


if __name__ == "__main__":
    run_dispatcher()