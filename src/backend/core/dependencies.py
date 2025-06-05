"""FastAPI dependencies for backend services."""

from elasticsearch import AsyncElasticsearch

from lex.core.clients import get_async_elasticsearch_client


async def get_es_client() -> AsyncElasticsearch:
    """Dependency to provide an async Elasticsearch client.

    Creates a fresh client for each request to avoid event loop issues.
    """
    return get_async_elasticsearch_client()
