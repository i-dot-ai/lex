import traceback
from typing import List

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.legislation.models import (
    LegislationActSearch,
    LegislationFullText,
    LegislationFullTextLookup,
    LegislationLookup,
    LegislationSectionLookup,
    LegislationSectionSearch,
    LegislationSearchResponse,
)
from backend.legislation.search import (
    get_legislation_full_text,
    get_legislation_sections,
    legislation_act_search,
    legislation_lookup,
    legislation_section_search,
)
from lex.legislation.models import Legislation, LegislationSection

router = APIRouter(
    prefix="/legislation",
    tags=["legislation"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/section/search",
    response_model=List[LegislationSection],
    operation_id="search_for_legislation_sections",
)
async def search_for_legislation_sections(
    search: LegislationSectionSearch):
    try:
        result = await legislation_section_search(search)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/search",
    response_model=LegislationSearchResponse,
    operation_id="search_for_legislation_acts",
)
async def search_for_legislation_acts(
    search: LegislationActSearch):
    try:
        result = await legislation_act_search(search)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/lookup",
    response_model=Legislation,
    operation_id="lookup_legislation",
    responses={404: {"description": "Legislation not found"}},
)
async def lookup_legislation_endpoint(
    lookup: LegislationLookup):
    try:
        result = await legislation_lookup(lookup)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Legislation not found: {lookup.legislation_type.value} {lookup.year} No. {lookup.number}",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/section/lookup",
    response_model=List[LegislationSection],
    operation_id="get_legislation_sections",
    responses={404: {"description": "No sections found for the specified legislation title"}},
)
async def get_sections_by_id(
    input: LegislationSectionLookup):
    try:
        sections = await get_legislation_sections(input)
        if not sections:
            raise HTTPException(
                status_code=404, detail=f"No sections found for legislation title: {input.title}"
            )
        return sections
    except HTTPException:
        raise
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/text",
    response_model=LegislationFullText,
    operation_id="get_legislation_full_text",
    responses={404: {"description": "Legislation not found"}},
)
async def get_full_text_by_id(
    input: LegislationFullTextLookup):
    try:
        result = await get_legislation_full_text(input)
        if not result:
            raise HTTPException(
                status_code=404, detail=f"Legislation not found: {input.legislation_id}"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.get(
    "/proxy/{legislation_id:path}",
    operation_id="proxy_legislation_data",
    responses={404: {"description": "Legislation not found"}, 502: {"description": "External API error"}},
)
async def proxy_legislation_data(legislation_id: str):
    """Proxy endpoint to fetch enriched metadata from legislation.gov.uk.

    Args:
        legislation_id: The legislation ID (e.g., "ukpga/2018/12")

    Returns:
        HTML content from legislation.gov.uk with CORS headers
    """
    try:
        # Build URL to legislation.gov.uk
        url = f"https://www.legislation.gov.uk/{legislation_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Legislation not found: {legislation_id}")

            response.raise_for_status()

            # Return the HTML content with appropriate headers
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "text/html"),
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                }
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"External API error: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)
