import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.core.error_handling import handle_errors
from backend.legislation.models import (
    LegislationActSearch,
    LegislationFullText,
    LegislationFullTextLookup,
    LegislationLookup,
    LegislationSearchResponse,
    LegislationSectionLookup,
    LegislationSectionSearch,
)
from backend.legislation.search import (
    get_legislation_full_text,
    get_legislation_sections,
    legislation_act_search,
    legislation_lookup,
    legislation_section_search,
)
from lex.legislation.models import Legislation, LegislationSection

logger = logging.getLogger(__name__)

# Simple in-memory cache for legislation HTML
# Format: {legislation_id: (content_bytes, content_type, cached_at)}
_html_cache: dict[str, tuple[bytes, str, datetime]] = {}
_CACHE_TTL = timedelta(hours=24)
_MAX_CACHE_SIZE = 1500  # ~750MB-1.5GB depending on doc sizes


def _get_cached_html(legislation_id: str) -> tuple[bytes, str] | None:
    """Get cached HTML if available and not expired."""
    if legislation_id in _html_cache:
        content, content_type, cached_at = _html_cache[legislation_id]
        if datetime.now() - cached_at < _CACHE_TTL:
            return (content, content_type)
        # Expired - remove it
        del _html_cache[legislation_id]
    return None


def _cache_html(legislation_id: str, content: bytes, content_type: str) -> None:
    """Cache HTML content with simple LRU eviction."""
    _html_cache[legislation_id] = (content, content_type, datetime.now())

    # Simple eviction: remove oldest if over limit
    if len(_html_cache) > _MAX_CACHE_SIZE:
        oldest_id = min(_html_cache.items(), key=lambda x: x[1][2])[0]
        del _html_cache[oldest_id]


router = APIRouter(
    prefix="/legislation",
    tags=["legislation"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/section/search",
    response_model=List[LegislationSection],
    operation_id="search_for_legislation_sections",
    summary="Search within specific sections of legislation",
    description="Find text within sections of Acts, SIs, or other legislation types. Use for detailed content searches.",
)
@handle_errors
async def search_for_legislation_sections(search: LegislationSectionSearch):
    return await legislation_section_search(search)


@router.post(
    "/search",
    response_model=LegislationSearchResponse,
    operation_id="search_for_legislation_acts",
    summary="Search for Acts and Statutory Instruments",
    description="Find legislation by title, content, or metadata. Returns full Acts and SIs with match scores.",
)
@handle_errors
async def search_for_legislation_acts(search: LegislationActSearch):
    return await legislation_act_search(search)


@router.post(
    "/lookup",
    response_model=Legislation,
    operation_id="lookup_legislation",
    summary="Get specific legislation by type, year, and number",
    description="Retrieve a single Act or SI using its official citation (e.g. ukpga/2018/12).",
    responses={404: {"description": "Legislation not found"}},
)
@handle_errors
async def lookup_legislation_endpoint(lookup: LegislationLookup):
    result = await legislation_lookup(lookup)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Legislation not found: {lookup.legislation_type.value} {lookup.year} No. {lookup.number}",
        )
    return result


@router.post(
    "/section/lookup",
    response_model=List[LegislationSection],
    operation_id="get_legislation_sections",
    summary="Get all sections for specific legislation",
    description="Retrieve the complete structure and content of all sections within a piece of legislation.",
    responses={404: {"description": "No sections found for the specified legislation title"}},
)
@handle_errors
async def get_sections_by_id(input: LegislationSectionLookup):
    sections = await get_legislation_sections(input)
    if not sections:
        raise HTTPException(
            status_code=404,
            detail=f"No sections found for legislation ID: {input.legislation_id}",
        )
    return sections


@router.post(
    "/text",
    response_model=LegislationFullText,
    operation_id="get_legislation_full_text",
    summary="Get complete text content of legislation",
    description="Retrieve the full text content of an Act or SI as a single document.",
    responses={404: {"description": "Legislation not found"}},
)
@handle_errors
async def get_full_text_by_id(input: LegislationFullTextLookup):
    result = await get_legislation_full_text(input)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Legislation not found: {input.legislation_id}"
        )
    return result


@router.get(
    "/proxy/{legislation_id:path}",
    operation_id="proxy_legislation_data",
    responses={
        404: {"description": "Legislation not found"},
        502: {"description": "External API error"},
    },
)
@handle_errors
async def proxy_legislation_data(legislation_id: str):
    """Proxy endpoint to fetch enriched metadata from legislation.gov.uk.

    Args:
        legislation_id: The legislation ID (e.g., "ukpga/2018/12")

    Returns:
        HTML content from legislation.gov.uk with CORS headers
    """
    try:
        # Check cache first
        cached = _get_cached_html(legislation_id)
        if cached:
            content, content_type = cached
            return Response(
                content=content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400",  # 24 hours
                    "X-Cache": "HIT",
                },
            )

        # Cache miss - fetch from legislation.gov.uk with retry logic
        url = f"https://www.legislation.gov.uk/{legislation_id}"

        # Retry logic for rate limiting (429/436) with exponential backoff
        max_retries = 5
        base_delay = 1.0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, follow_redirects=True)

                    # Handle rate limiting - retry with exponential backoff
                    if response.status_code in [429, 436]:
                        if attempt < max_retries - 1:
                            # Calculate backoff delay
                            delay = base_delay * (2**attempt)
                            retry_after = response.headers.get("Retry-After")
                            if retry_after:
                                try:
                                    delay = int(retry_after)
                                except ValueError:
                                    pass

                            logger.warning(
                                f"Rate limited (HTTP {response.status_code}) fetching {url}, "
                                f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        else:
                            # Final attempt failed
                            raise HTTPException(
                                status_code=429,
                                detail="Rate limited by external API. Please try again later.",
                            )

                    if response.status_code == 404:
                        raise HTTPException(
                            status_code=404, detail=f"Legislation not found: {legislation_id}"
                        )

                    response.raise_for_status()

                    # Cache the response
                    content_type = response.headers.get("content-type", "text/html")
                    _cache_html(legislation_id, response.content, content_type)

                    # Return the HTML content with appropriate headers
                    return Response(
                        content=response.content,
                        media_type=content_type,
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "public, max-age=86400",  # 24 hours
                            "X-Cache": "MISS",
                        },
                    )

                except httpx.HTTPStatusError as e:
                    # Let other HTTP errors (non-429/436) fall through
                    if e.response.status_code not in [429, 436]:
                        raise HTTPException(status_code=502, detail=f"External API error: {str(e)}")
                    # For 429/436, continue to next retry iteration
                    continue

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"External API error: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request failed: {str(e)}")
