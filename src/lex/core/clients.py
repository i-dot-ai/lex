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
    # Common configuration for better resilience
    common_config = {
        "request_timeout": 60,  # Increased from 30s
        "max_retries": 5,  # Retry on connection failures
        "retry_on_timeout": True,  # Retry on timeout
        "retry_on_status": [502, 503, 504],  # Retry on server errors
        # Connection pool settings for better resilience
        "http_compress": True,  # Compress requests to reduce bandwidth
        "connections_per_node": 10,  # Connection pool size
    }

    # Check if we're using Elastic Cloud
    if ELASTIC_MODE == "cloud" and ELASTIC_CLOUD_ID:
        # Cloud configuration with API key if available
        if ELASTIC_API_KEY:
            client = Elasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                api_key=ELASTIC_API_KEY,
                **common_config
            )
        # Cloud configuration with username/password
        elif ELASTIC_USERNAME and ELASTIC_PASSWORD:
            client = Elasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                basic_auth=(ELASTIC_USERNAME, ELASTIC_PASSWORD),
                **common_config
            )
        else:
            logger.error("Missing Elastic Cloud credentials (API key or username/password)")
            return None
    else:
        # Local configuration
        client = Elasticsearch(
            ELASTIC_HOST, 
            **common_config,
            # Additional settings for local deployments
            sniff_on_start=False,  # Don't sniff on start to avoid connection issues
            sniff_on_connection_fail=False,  # Don't sniff on failure
        )

    try:
        # Test connection with a timeout
        info = client.info(request_timeout=10)
        logger.info(
            f"Connected to Elasticsearch cluster: {info.get('cluster_name', 'unknown')}",
            extra={
                "cluster_name": info.get('cluster_name'),
                "version": info.get('version', {}).get('number'),
            }
        )
        return client
    except Exception as e:
        logger.error(f"Error connecting to Elasticsearch: {e}")
        return None


def get_async_elasticsearch_client() -> AsyncElasticsearch:
    """
    Returns an AsyncElasticsearch client based on the configured settings.

    Returns:
        AsyncElasticsearch: Configured AsyncElasticsearch client or None if connection fails
    """
    # Common configuration for better resilience
    common_config = {
        "request_timeout": 60,  # Increased from 30s
        "max_retries": 5,  # Retry on connection failures
        "retry_on_timeout": True,  # Retry on timeout
        "retry_on_status": [502, 503, 504],  # Retry on server errors
        # Connection pool settings
        "http_compress": True,  # Compress requests
        "connections_per_node": 10,  # Connection pool size
    }

    # Check if we're using Elastic Cloud
    if ELASTIC_MODE == "cloud" and ELASTIC_CLOUD_ID:
        # Cloud configuration with API key if available
        if ELASTIC_API_KEY:
            client = AsyncElasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                api_key=ELASTIC_API_KEY,
                **common_config
            )
        # Cloud configuration with username/password
        elif ELASTIC_USERNAME and ELASTIC_PASSWORD:
            client = AsyncElasticsearch(
                cloud_id=ELASTIC_CLOUD_ID,
                basic_auth=(ELASTIC_USERNAME, ELASTIC_PASSWORD),
                **common_config
            )
        else:
            logger.error("Missing Elastic Cloud credentials (API key or username/password)")
            return None
    else:
        # Local configuration
        client = AsyncElasticsearch(
            ELASTIC_HOST,
            **common_config,
            # Additional settings for local deployments
            sniff_on_start=False,  # Don't sniff on start
            sniff_on_connection_fail=False,  # Don't sniff on failure
        )

    return client


es_client = get_elasticsearch_client()
async_es_client = get_async_elasticsearch_client()
