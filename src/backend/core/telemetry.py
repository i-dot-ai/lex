"""OpenTelemetry and Azure Monitor configuration."""

import logging

from backend.core.config import APPLICATIONINSIGHTS_CONNECTION_STRING

logger = logging.getLogger(__name__)

_azure_monitor_configured = False
_instrumented_apps: set[int] = set()


def configure_telemetry():
    """Configure Azure Monitor OpenTelemetry and logging."""
    global _azure_monitor_configured

    # Configure Azure Monitor OpenTelemetry FIRST - before any FastAPI imports
    if APPLICATIONINSIGHTS_CONNECTION_STRING and not _azure_monitor_configured:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor()
        _azure_monitor_configured = True
        logger.info("Azure Monitor OpenTelemetry configured")

    # Configure logging to show all INFO level logs
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Ensure lex.core.embeddings logger shows INFO logs
    logging.getLogger("lex.core.embeddings").setLevel(logging.INFO)


def is_azure_monitor_configured() -> bool:
    """Check if Azure Monitor has already been configured."""
    return _azure_monitor_configured


def instrument_fastapi_app(app):
    """Add FastAPI instrumentation for Azure Monitor telemetry (idempotent)."""
    app_id = id(app)
    if app_id in _instrumented_apps:
        return

    if APPLICATIONINSIGHTS_CONNECTION_STRING:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
            _instrumented_apps.add(app_id)
            logger.info("FastAPI app instrumented for Azure Monitor")
        except Exception as e:
            logger.warning(f"FastAPI instrumentation failed: {e}")
