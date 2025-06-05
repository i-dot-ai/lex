import os

# Index names from environment variables
CASELAW_INDEX = os.getenv("ELASTIC_CASELAW_INDEX", "lex-dev-caselaw")
CASELAW_SECTION_INDEX = os.getenv("ELASTIC_CASELAW_SECTION_INDEX", "lex-dev-caselaw-section")
LEGISLATION_INDEX = os.getenv("ELASTIC_LEGISLATION_INDEX", "lex-dev-legislation")
LEGISLATION_SECTION_INDEX = os.getenv(
    "ELASTIC_LEGISLATION_SECTION_INDEX", "lex-dev-legislation-section"
)
EXPLANATORY_NOTE_INDEX = os.getenv("ELASTIC_EXPLANATORY_NOTE_INDEX", "lex-dev-explanatory-note")
AMENDMENT_INDEX = os.getenv("ELASTIC_AMENDMENT_INDEX", "lex-dev-amendment")
INFERENCE_ID = os.getenv("ELASTIC_INFERENCE_ID", "lex-dev-inference-endpoint")

# Elasticsearch configuration
ELASTIC_MODE = os.environ.get("ELASTIC_MODE", "local")
ELASTIC_HOST = os.environ.get("ELASTIC_HOST", "http://localhost:9200")
ELASTIC_CLOUD_ID = os.environ.get("ELASTIC_CLOUD_ID", "")
ELASTIC_API_KEY = os.environ.get("ELASTIC_API_KEY", "")
ELASTIC_USERNAME = os.environ.get("ELASTIC_USERNAME", "")
ELASTIC_PASSWORD = os.environ.get("ELASTIC_PASSWORD", "")

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

YEARS = list(range(1267, 2024))

EMBEDDING_DIMENSIONS = 1024
EMBEDDING_MODEL = "text-embedding-3-large"
