import os
from datetime import datetime

# Qdrant configuration
USE_CLOUD_QDRANT = os.environ.get("USE_CLOUD_QDRANT", "false").lower() == "true"

# Local Qdrant (default)
QDRANT_HOST = os.environ.get("QDRANT_HOST", "http://localhost:6333")
QDRANT_GRPC_PORT = int(os.environ.get("QDRANT_GRPC_PORT", "6334"))
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", None)

# Cloud Qdrant (when USE_CLOUD_QDRANT=true)
QDRANT_CLOUD_URL = os.environ.get("QDRANT_CLOUD_URL")
QDRANT_CLOUD_API_KEY = os.environ.get("QDRANT_CLOUD_API_KEY")

# Collection names (replacing index names)
LEGISLATION_COLLECTION = "legislation"
LEGISLATION_SECTION_COLLECTION = "legislation_section"
CASELAW_COLLECTION = "caselaw"
CASELAW_SECTION_COLLECTION = "caselaw_section"
CASELAW_SUMMARY_COLLECTION = "caselaw_summary"
EXPLANATORY_NOTE_COLLECTION = "explanatory_note"
AMENDMENT_COLLECTION = "amendment"

LEGISLATION_TYPE_MAPPING = {
    "primary": ["ukpga", "asp", "asc", "anaw", "ukcm", "nia"],
    "secondary": ["wsi", "uksi", "ssi", "nisr"],
    "european": ["eudn", "eudr", "eur"],
}

# Dynamically calculate years up to current year
CURRENT_YEAR = datetime.now().year
YEARS = list(range(1267, CURRENT_YEAR + 1))  # Includes current year

# Azure OpenAI embedding configuration
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

# PostHog Analytics configuration (cookieless, EU region, GDPR compliant)
POSTHOG_KEY = os.environ.get("POSTHOG_KEY", "")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://eu.i.posthog.com")

# Bulk Downloads configuration
DOWNLOADS_BASE_URL = os.environ.get(
    "DOWNLOADS_BASE_URL", "https://lexdownloads.blob.core.windows.net/downloads"
)
