import logging
import socket
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)


# This code isn't used elsewhere in the codebase, but we're keeping it here to enable others to extend the functionality.
class ElasticsearchLogHandler(logging.Handler):
    """Logging handler that sends logs to Elasticsearch.

    This handler formats log records as JSON documents and sends them
    to an Elasticsearch index.
    """

    def __init__(
        self, es_client: Elasticsearch, index_name: str, service_name: str, environment: str
    ) -> None:
        """Initialize the handler with Elasticsearch client and index details.

        Args:
            es_client: Elasticsearch client instance
            index_name (str): Name of the Elasticsearch index to write logs to
            service_name (str): Name of the service (e.g., "frontend", "pipeline")
            environment (str): Environment name (e.g., "localhost", "dev", "prod")
        """
        super().__init__()
        self.es_client = es_client
        self.index_name = index_name
        self.service_name = service_name
        self.environment = environment
        self.hostname: str = socket.gethostname()

        # Create the index if it doesn't exist
        if not es_client.indices.exists(index=index_name):
            es_client.indices.create(index=index_name)

    def emit(self, record: logging.LogRecord) -> None:
        """Format and send the log record to Elasticsearch.

        Args:
            record: Log record to format and send
        """
        # Skip processing if no client is available
        if not self.es_client:
            return

        try:
            # Format exception info if present
            exc_info: Optional[str] = None
            if record.exc_info:
                exc_info = "".join(traceback.format_exception(*record.exc_info))

            # Create the log document
            doc: Dict[str, Any] = {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                    timespec="microseconds"
                ),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "service": self.service_name,
                "environment": self.environment,
                "hostname": self.hostname,
                "path": record.pathname,
                "function": record.funcName,
                "line_number": record.lineno,
                "thread": record.thread,
                "thread_name": record.threadName,
                "process": record.process,
            }

            # Add exception info if present
            if exc_info:
                doc["exception"] = exc_info

            # Add any extra fields from the record
            # Check for props attribute (legacy support)
            if hasattr(record, "props"):
                doc.update(record.props)

            # Add fields from extra parameter (standard Python logging)
            # Get all custom attributes added via extra parameter
            for key, value in record.__dict__.items():
                if key not in [
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "thread",
                    "threadName",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ]:
                    doc[key] = value

            # Send to Elasticsearch
            self.es_client.index(index=self.index_name, id=str(uuid4()), body=doc)

        except Exception as e:
            # Handle any errors during processing to avoid log handler loops
            sys.stderr.write(f"Error in ElasticsearchLogHandler: {str(e)}\n")


def setup_elasticsearch_logging(
    es_client: Optional[Elasticsearch],
    index_name: str,
    service_name: str,
    environment: str,
    log_level: int = logging.INFO,
) -> Optional[ElasticsearchLogHandler]:
    """Set up logging to Elasticsearch for a specific service.

    Args:
        es_client: Elasticsearch client
        index_name (str): Name of the index to log to
        service_name (str): Name of the service (e.g., "frontend", "pipeline")
        environment (str): Environment name (e.g., "localhost", "dev", "prod")
        log_level: Logging level to use

    Returns:
        ElasticsearchLogHandler: The configured handler
    """
    if not es_client:
        logger.warning("No Elasticsearch client provided, skipping Elasticsearch logging setup")
        return None

    # Create and configure the handler
    handler = ElasticsearchLogHandler(
        es_client=es_client,
        index_name=index_name,
        service_name=service_name,
        environment=environment,
    )
    handler.setLevel(log_level)

    # Add the handler to the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    # Log a test message
    logger.info(
        f"Elasticsearch logging initialized for service {service_name} to index {index_name}"
    )

    return handler
