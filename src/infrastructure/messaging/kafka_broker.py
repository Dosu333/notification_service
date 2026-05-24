import json
from typing import Dict, Any
from confluent_kafka import Producer
from src.interfaces.messaging import MessageBroker


class KafkaMessageBroker(MessageBroker):
    def __init__(self, bootstrap_servers: str):
        # Initialize Kafka producer
        self.producer = Producer({'bootstrap.servers': bootstrap_servers})

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Serializes the dictionary to JSON and sends it to broker."""
        self.producer.produce(
            topic=topic,
            value=json.dumps(payload).encode('utf-8')
        )
        self.producer.poll(0)

    def flush(self):
        """Blocks until all queued messages are delivered to the broker."""
        self.producer.flush()