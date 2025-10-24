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
EXPLANATORY_NOTE_COLLECTION = "explanatory_note"
AMENDMENT_COLLECTION = "amendment"

LEGISLATION_TYPES = [
    "ukpga",
    "asp",
    "asc",
    "anaw",
    "wsi",
    "uksi",
    "ssi",
    "ukcm",
    "nisr",
    "nia",
    "eudn",
    "eudr",
    "eur",
    "ukla",
    "ukppa",
    "apni",
    "gbla",
    "aosp",
    "aep",
    "apgb",
    "mwa",
    "aip",
    "mnia",
    "nisro",
    "nisi",
    "uksro",
    "ukmo",
    "ukci",
]

LEGISLATION_TYPE_MAPPING = {
    "primary": ["ukpga", "asp", "asc", "anaw", "ukcm", "nia"],
    "secondary": ["wsi", "uksi", "ssi", "nisr"],
    "european": ["eudn", "eudr", "eur"],
}

LEGISLATION_NAME_MAPPING = {
    "ukpga": "UK Public General Acts",
    "asp": "Acts of the Scottish Parliament",
    "asc": "Acts of Senedd Cymru",
    "anaw": "Acts of the National Assembly for Wales",
    "wsi": "Wales Statutory Instruments",
    "uksi": "UK Statutory Instruments",
    "ssi": "Scottish Statutory Instruments",
    "ukcm": "Church Measures",
    "nisr": "Northern Ireland Statutory Rules",
    "nia": "Acts of the Northern Ireland Assembly",
    "eudn": "Decisions originating from the EU",
    "eudr": "Directives originating from the EU",
    "eur": "Regulations originating from the EU",
    "ukla": "UK Local Acts",
    "ukppa": "UK Private and Personal Acts",
    "apni": "Acts of the Northern Ireland Parliament",
    "gbla": "Local Acts of the Parliament of Great Britain",
    "aosp": "Acts of the Old Scottish Parliament",
    "aep": "Acts of the English Parliament",
    "apgb": "Acts of the Parliament of Great Britain",
    "mwa": "Measures of the Welsh Assembly",
    "aip": "Acts of the Old Irish Parliament",
    "mnia": "Measures of the Northern Ireland Assembly",
    "nisro": "Northern Ireland Statutory Rules and Orders",
    "nisi": "Northern Ireland Orders in Council",
    "uksro": "UK Statutory Rules and Orders",
    "ukmo": "Uk Ministerial Orders",
    "ukci": "Church Instruments",
}

# Dynamically calculate years up to current year
CURRENT_YEAR = datetime.now().year
YEARS = list(range(1267, CURRENT_YEAR + 1))  # Includes current year

# Azure OpenAI embedding configuration
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
