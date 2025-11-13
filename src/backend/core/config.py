"""Configuration and environment variables."""

import os

# Rate limiting configuration
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))

# Cache TTL configuration 
DEFAULT_CACHE_TTL = int(os.getenv("DEFAULT_CACHE_TTL", "28800"))  # 8 hours
RATE_LIMIT_TTL_MINUTE = 60
RATE_LIMIT_TTL_HOUR = 3600

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# Azure Monitor configuration
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")