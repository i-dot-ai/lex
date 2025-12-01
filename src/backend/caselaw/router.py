from typing import List

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
    response_model=List[CaselawSection],
    operation_id="search_for_caselaw_section",
    summary="Search within specific case sections",
    description="Find text within judgments, headnotes, or specific parts of court cases.",
)
@handle_errors
async def search_caselaw_section_endpoint(search: CaselawSectionSearch):
    return await caselaw_section_search(search)


@router.post(
    "/reference/search",
    response_model=List[Caselaw],
    operation_id="search_for_caselaw_by_reference",
    summary="Find cases that cite specific cases or legislation",
    description="Search for cases that reference a particular case or Act. Filter by court, division, and date range.",
)
@handle_errors
async def search_caselaw_reference_endpoint(search: CaselawReferenceSearch):
    return await caselaw_reference_search(search)


@router.post(
    "/reference",
    response_model=List[Caselaw],
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
        # Build URL to caselaw.nationalarchives.gov.uk
        url = f"https://caselaw.nationalarchives.gov.uk/{case_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

            response.raise_for_status()

            # Return the HTML content with appropriate headers
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "text/html"),
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                },
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"External API error: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request failed: {str(e)}")
