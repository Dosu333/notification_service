import json
import logging
import uuid
from typing import Dict, Any, Callable, Optional
from confluent_kafka import Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic 
from src.interfaces.messaging import MessageConsumer, MessageBroker
from src.interfaces.metrics import MetricsService
from src.infrastructure.observability.logger import set_correlation_id

logger = logging.getLogger(__name__)


class KafkaMessageConsumer(MessageConsumer):
    def __init__(
        self, 
        bootstrap_servers: str, 
        group_id: str,
        dlq_broker: Optional[MessageBroker] = None,
        dlq_topic: str = "notification.dlq",
        metrics_service: Optional[MetricsService] = None
    ):
        self.bootstrap_servers = bootstrap_servers
        
        conf = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest', 
            'enable.auto.commit': False,
            'topic.metadata.refresh.interval.ms': 5000,
            'allow.auto.create.topics': True
        }
        self.consumer = Consumer(conf)
        self.group_id = group_id
        self.dlq_broker = dlq_broker
        self.dlq_topic = dlq_topic
        self.metrics_service = metrics_service

    def _ensure_topic_exists(self, topic: str) -> None:
        """🚨 Self-Healing: Programmatically creates the topic if it does not exist."""
        admin = AdminClient({'bootstrap.servers': self.bootstrap_servers})
        new_topic = NewTopic(topic, num_partitions=8, replication_factor=1)
        
        futures = admin.create_topics([new_topic])
        for t, future in futures.items():
            try:
                future.result()
                logger.info(f"Infrastructure: Auto-provisioned missing topic '{t}'")
            except Exception as e:
                if "TOPIC_ALREADY_EXISTS" not in str(e).upper():
                    logger.debug(f"Topic check for '{t}': {e}")

    def _send_to_dlq(self, raw_value: str, error_msg: str, topic: str = "unknown") -> None:
        """Helper method to park failed messages safely."""
        if self.metrics_service:
            self.metrics_service.increment_counter(
                metric_name="dlq_messages_total",
                tags={"topic": topic, "reason": "processing_failure"}
            )

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

    def start_consuming(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._ensure_topic_exists(topic)
        self._ensure_topic_exists(self.dlq_topic)
        
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to '{topic}' as '{self.group_id}'. Waiting for messages...")

        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error(f"Kafka Consumer Error: {msg.error()}")
                    continue
                
                # Default to a new UUID if no correlation ID is found in headers
                correlation_id = str(uuid.uuid4()) 
                
                if msg.headers():
                    for key, value in msg.headers():
                        if key == "x-correlation-id" and value:
                            correlation_id = value.decode('utf-8')
                            break
                
                # Bind ID to this worker's current execution cycle
                set_correlation_id(correlation_id)
                raw_value = msg.value().decode('utf-8')

                try:
                    payload = json.loads(raw_value)
                    handler(payload)
                    
                    self.consumer.commit(asynchronous=False)
                    logger.debug(f"Successfully processed and committed message from {topic}.")

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
