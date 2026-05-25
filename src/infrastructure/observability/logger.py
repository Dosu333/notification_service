import logging
import contextvars
from pythonjsonlogger import jsonlogger


correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="SYSTEM"
)


def set_correlation_id(correlation_id: str) -> None:
    """Helper to set the ID at the start of a request/message."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Helper to retrieve the current ID."""
    return correlation_id_var.get()


class CorrelationJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(
        self, 
        log_record: dict, 
        record: logging.LogRecord, 
        message_dict: dict
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        
        log_record['correlation_id'] = correlation_id_var.get()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name


def configure_json_logging(level: int = logging.INFO) -> None:
    """
    Overrides the default Python logging configuration to force all output 
    into JSON format with correlation IDs.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear out any existing handlers to prevent duplicate logs or non-JSON output
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Setup new JSON handler
    log_handler = logging.StreamHandler()
    
    # Define base fields for JSON logs and include correlation_id
    formatter = CorrelationJsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)
    
    # Silence overly verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)
