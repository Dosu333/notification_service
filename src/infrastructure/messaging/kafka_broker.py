import json
import logging
from typing import Dict, Any
from confluent_kafka import Producer
from src.interfaces.messaging import MessageBroker
from src.infrastructure.observability.logger import get_correlation_id


logger = logging.getLogger(__name__)


class KafkaMessageBroker(MessageBroker):
    def __init__(self, bootstrap_servers: str):
        conf = {'bootstrap.servers': bootstrap_servers}
        self.producer = Producer(conf)

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        raw_value = json.dumps(payload).encode('utf-8')
        correlation_id = get_correlation_id()
        
        headers = [("x-correlation-id", correlation_id.encode('utf-8'))]

        self.producer.produce(
            topic=topic,
            value=raw_value,
            headers=headers,
            callback=self._delivery_report
        )
        self.producer.poll(0)
        logger.debug(f"Queued message for topic {topic} with correlation_id {correlation_id}")

    def flush(self) -> None:
        self.producer.flush()

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
