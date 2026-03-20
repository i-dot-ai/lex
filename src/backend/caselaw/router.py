import logging
from collections import OrderedDict
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.caselaw.models import (
    CaselawReferenceSearch,
    CaselawSearch,
    CaselawSearchResponse,
    CaselawSectionSearch,
    CaselawSummarySearch,
    CaselawSummarySearchResponse,
)
from backend.caselaw.search import (
    caselaw_reference_search,
    caselaw_search,
    caselaw_section_search,
    caselaw_summary_search,
)
from backend.core.error_handling import handle_errors
from lex.caselaw.models import Caselaw, CaselawSection

logger = logging.getLogger(__name__)

# Shared httpx client — reuses TCP connections across requests
_http_client: httpx.AsyncClient | None = None

# Simple in-memory cache for caselaw HTML
# Format: {case_id: (content_bytes, content_type, cached_at)}
_html_cache: OrderedDict[str, tuple[bytes, str, datetime]] = OrderedDict()
_CACHE_TTL = timedelta(hours=24)
_MAX_CACHE_SIZE = 200


def _get_http_client() -> httpx.AsyncClient:
    """Get or create the shared httpx client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


def _get_cached_html(case_id: str) -> tuple[bytes, str] | None:
    """Get cached HTML if available and not expired."""
    if case_id in _html_cache:
        content, content_type, cached_at = _html_cache[case_id]
        if datetime.now() - cached_at < _CACHE_TTL:
            _html_cache.move_to_end(case_id)
            return (content, content_type)
        del _html_cache[case_id]
    return None


def _cache_html(case_id: str, content: bytes, content_type: str) -> None:
    """Cache HTML content with O(1) LRU eviction."""
    _html_cache[case_id] = (content, content_type, datetime.now())
    _html_cache.move_to_end(case_id)
    while len(_html_cache) > _MAX_CACHE_SIZE:
        _html_cache.popitem(last=False)


router = APIRouter(
    prefix="/caselaw",
    tags=["caselaw"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/search",
    response_model=CaselawSearchResponse,
    operation_id="search_for_caselaw",
    summary="Search court cases and judgments",
    description="Find cases by content, court, judge, or citation. Returns cases with match scores and metadata.",
)
@handle_errors
async def search_caselaw_endpoint(search: CaselawSearch):
    return await caselaw_search(search)


@router.post(
    "/section/search",
    response_model=list[CaselawSection],
    operation_id="search_for_caselaw_section",
    summary="Search within specific case sections",
    description="Find text within judgments, headnotes, or specific parts of court cases.",
)
@handle_errors
async def search_caselaw_section_endpoint(search: CaselawSectionSearch):
    return await caselaw_section_search(search)


@router.post(
    "/reference/search",
    response_model=list[Caselaw],
    operation_id="search_for_caselaw_by_reference",
    summary="Find cases that cite specific cases or legislation",
    description="Search for cases that reference a particular case or Act. Filter by court, division, and date range.",
)
@handle_errors
async def search_caselaw_reference_endpoint(search: CaselawReferenceSearch):
    return await caselaw_reference_search(search)


@router.post(
    "/reference",
    response_model=list[Caselaw],
    operation_id="search_caselaw_by_reference",
    summary="Find cases that cite specific cases or legislation (MCP alias)",
    description="Search for cases that reference a particular case or Act. Alias for /reference/search.",
)
async def search_caselaw_reference_alias(search: CaselawReferenceSearch):
    return await search_caselaw_reference_endpoint(search)


@router.post(
    "/summary/search",
    response_model=CaselawSummarySearchResponse,
    operation_id="search_caselaw_summaries",
    summary="Search AI-generated case summaries",
    description=(
        "Find cases by AI-generated summaries. Returns concise results suitable for "
        "AI agents. Summaries include material facts, legal issues, ratio decidendi, "
        "reasoning, and obiter dicta."
    ),
)
@handle_errors
async def search_caselaw_summaries_endpoint(search: CaselawSummarySearch):
    return await caselaw_summary_search(search)


@router.get(
    "/proxy/{case_id:path}",
    operation_id="proxy_caselaw_data",
    responses={404: {"description": "Case not found"}, 502: {"description": "External API error"}},
)
@handle_errors
async def proxy_caselaw_data(case_id: str):
    """Proxy endpoint to fetch enriched metadata from caselaw.nationalarchives.gov.uk.

    Args:
        case_id: The case ID (e.g., "uksc/2024/15")

    Returns:
        HTML content from caselaw.nationalarchives.gov.uk with CORS headers
    """
    try:
        # Check cache first
        cached = _get_cached_html(case_id)
        if cached:
            content, content_type = cached
            return Response(
                content=content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600",
                    "X-Cache": "HIT",
                },
            )

        # Cache miss — fetch from caselaw.nationalarchives.gov.uk
        url = f"https://caselaw.nationalarchives.gov.uk/{case_id}"
        client = _get_http_client()
        response = await client.get(url, follow_redirects=True)

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        response.raise_for_status()

        content_type = response.headers.get("content-type", "text/html")
        _cache_html(case_id, response.content, content_type)

        return Response(
            content=response.content,
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600",
                "X-Cache": "MISS",
            },
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"External API error: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request failed: {str(e)}")
