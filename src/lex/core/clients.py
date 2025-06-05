import logging

from elasticsearch import AsyncElasticsearch, Elasticsearch

from lex.settings import (
    ELASTIC_API_KEY,
    ELASTIC_CLOUD_ID,
    ELASTIC_HOST,
    ELASTIC_MODE,
    ELASTIC_PASSWORD,
    ELASTIC_USERNAME,
)

logger = logging.getLogger(__name__)


def get_elasticsearch_client() -> Elasticsearch:
    """
    Returns an Elasticsearch client based on the configured settings.

    Returns:
        Elasticsearch: Configured Elasticsearch client or None if connection fails
    """

    # Check if we're using Elastic Cloud
    if ELASTIC_MODE == "cloud" and ELASTIC_CLOUD_ID:
        # Cloud configuration with API key if available
        if ELASTIC_API_KEY:
            client = Elasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                api_key=ELASTIC_API_KEY,
                request_timeout=30,
            )
        # Cloud configuration with username/password
        elif ELASTIC_USERNAME and ELASTIC_PASSWORD:
            client = Elasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                basic_auth=(ELASTIC_USERNAME, ELASTIC_PASSWORD),
                request_timeout=30,
            )
        else:
            logger.error("Missing Elastic Cloud credentials (API key or username/password)")
            return None
    else:
        # Local configuration
        client = Elasticsearch(ELASTIC_HOST, request_timeout=30)

    try:
        client.info()
        logger.info("Connected to Elasticsearch")
        return client
    except Exception as e:
        logger.error(f"Error connecting to Elasticsearch: {e}")
        return None


def get_async_elasticsearch_client() -> AsyncElasticsearch:
    """
    Returns an AsyncElasticsearch client based on the configured settings.

    Returns:
        Elasticsearch: Configured Elasticsearch client or None if connection fails
    """

    # Check if we're using Elastic Cloud
    if ELASTIC_MODE == "cloud" and ELASTIC_CLOUD_ID:
        # Cloud configuration with API key if available
        if ELASTIC_API_KEY:
            client = AsyncElasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                api_key=ELASTIC_API_KEY,
                request_timeout=30,
            )
        # Cloud configuration with username/password
        elif ELASTIC_USERNAME and ELASTIC_PASSWORD:
            client = AsyncElasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                basic_auth=(ELASTIC_USERNAME, ELASTIC_PASSWORD),
                request_timeout=30,
            )
        else:
            logger.error("Missing Elastic Cloud credentials (API key or username/password)")
            return None
    else:
        # Local configuration
        client = AsyncElasticsearch(ELASTIC_HOST, request_timeout=30)

    return client


es_client = get_elasticsearch_client()
async_es_client = get_async_elasticsearch_client()
