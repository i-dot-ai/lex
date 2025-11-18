"""Lex API main entry point."""

import uvicorn

from backend.api.app import create_app
from backend.core.telemetry import configure_telemetry

# Configure telemetry first
configure_telemetry()

# Create the application
app = create_app()

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
