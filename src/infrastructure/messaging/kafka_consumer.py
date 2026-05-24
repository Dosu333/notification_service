import json
import logging
from typing import Dict, Any, Callable
from confluent_kafka import Consumer, KafkaError
from src.interfaces.messaging import MessageConsumer


logger = logging.getLogger(__name__)


class KafkaMessageConsumer(MessageConsumer):
    def __init__(self, bootstrap_servers: str, group_id: str):
        # Configuration for Kafka Consumer
        conf = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        }
        self.consumer = Consumer(conf)

    def start_consuming(
        self, 
        topic: str, 
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to topic '{topic}' as group '{self.consumer.consumer_group}'. Waiting for messages...")

        try:
            while True:
                # Poll for messages with timeout to allow graceful shutdown
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka Consumer Error: {msg.error()}")
                        continue
                    
                try:
                    # Deserialize bytes into dictionary
                    raw_value = msg.value().decode('utf-8')
                    payload = json.loads(raw_value)
                    
                    # Execute the provided handler function with the payload
                    handler(payload)

                    # If processing is successful, commit the offset to avoid reprocessing
                    self.consumer.commit(asynchronous=False)
                    logger.debug(f"Successfully processed and committed message from {topic}.")

                except json.JSONDecodeError as e:
                    # TODO: Send to DLQ first.
                    logger.error(f"Fatal JSON decode error. Skipping poison pill message. {e}")
                    self.consumer.commit(asynchronous=False)
                    
                except Exception as e:
                    logger.error(f"Failed to process message due to application error: {e}. Offset NOT committed.")
                    
        except KeyboardInterrupt:
            logger.info("Consumer manually stopped.")
        finally:
            self.consumer.close()
