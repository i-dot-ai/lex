"""FastAPI dependencies for backend services."""

import os
from typing import Annotated

from elasticsearch import AsyncElasticsearch
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from lex.core.clients import get_async_elasticsearch_client

# Security scheme
security = HTTPBearer()

# Load API key from environment
API_KEY = os.getenv("LEX_API_KEY")


async def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)],
) -> str:
    """Verify the API key from the Authorization header.

    Expects: Authorization: Bearer <api-key>
    """
    if not API_KEY:
        # If no API key is configured, allow all requests
        return credentials.credentials

    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_es_client() -> AsyncElasticsearch:
    """Dependency to provide an async Elasticsearch client.

    Creates a fresh client for each request to avoid event loop issues.
    """
    return get_async_elasticsearch_client()
