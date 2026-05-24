import json
import logging
from typing import Dict, Any, Callable, Optional
from confluent_kafka import Consumer, KafkaError
from src.interfaces.messaging import MessageConsumer, MessageBroker


logger = logging.getLogger(__name__)


class KafkaMessageConsumer(MessageConsumer):
    def __init__(
        self, 
        bootstrap_servers: str, 
        group_id: str,
        dlq_broker: Optional[MessageBroker] = None,
        dlq_topic: str = "notification.dlq"
    ):
        conf = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest', 
            'enable.auto.commit': False      
        }
        self.consumer = Consumer(conf)
        self.dlq_broker = dlq_broker
        self.dlq_topic = dlq_topic

    def _send_to_dlq(self, raw_value: str, error_msg: str) -> None:
        """Helper method to park failed messages safely."""
        if not self.dlq_broker:
            logger.warning("No DLQ broker configured. Message is being skipped and dropped permanently.")
            return
        
        dlq_payload = {
            "original_message": raw_value,
            "error_reason": error_msg
        }
        
        try:
            self.dlq_broker.publish(topic=self.dlq_topic, payload=dlq_payload)
            self.dlq_broker.flush()
            logger.info(f"Message successfully routed to DLQ topic: {self.dlq_topic}")
        except Exception as e:
            logger.critical(f"FATAL: Failed to publish to DLQ. Message lost! Error: {e}")

    def start_consuming(
        self, 
        topic: str, 
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to '{topic}' as '{self.consumer.consumer_group}'. Waiting for messages...")

        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error(f"Kafka Consumer Error: {msg.error()}")
                    continue

                raw_value = msg.value().decode('utf-8')

                try:
                    payload = json.loads(raw_value)
                    
                    # Process the message with the provided handler
                    handler(payload)

                    self.consumer.commit(asynchronous=False)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error. Routing to DLQ. Error: {e}")
                    self._send_to_dlq(raw_value, str(e))
                    self.consumer.commit(asynchronous=False)
                    
                except Exception as e:
                    logger.error(f"Application processing failed. Routing to DLQ. Error: {e}")
                    self._send_to_dlq(raw_value, str(e))
                    self.consumer.commit(asynchronous=False)
                    
        except KeyboardInterrupt:
            logger.info("Consumer manually stopped.")
        finally:
            self.consumer.close()
