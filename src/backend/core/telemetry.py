"""OpenTelemetry and Azure Monitor configuration."""

import logging
import os

from backend.core.config import APPLICATIONINSIGHTS_CONNECTION_STRING


def configure_telemetry():
    """Configure Azure Monitor OpenTelemetry and logging."""
    # Configure Azure Monitor OpenTelemetry FIRST - before any FastAPI imports
    if APPLICATIONINSIGHTS_CONNECTION_STRING:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor()
        print("✅ Azure Monitor OpenTelemetry configured")

    # Configure logging to show all INFO level logs
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Ensure lex.core.embeddings logger shows INFO logs
    logging.getLogger("lex.core.embeddings").setLevel(logging.INFO)


def instrument_fastapi_app(app):
    """Add FastAPI instrumentation for Azure Monitor telemetry."""
    if APPLICATIONINSIGHTS_CONNECTION_STRING:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
            print("✅ FastAPI app instrumented for Azure Monitor")
        except Exception as e:
            print(f"⚠️ FastAPI instrumentation failed: {e}")