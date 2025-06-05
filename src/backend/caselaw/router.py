import traceback
from typing import List

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException

from backend.caselaw.models import CaselawReferenceSearch, CaselawSearch, CaselawSectionSearch
from backend.caselaw.search import caselaw_reference_search, caselaw_search, caselaw_section_search
from backend.core.dependencies import get_es_client
from lex.caselaw.models import Caselaw, CaselawSection

router = APIRouter(
    prefix="/caselaw",
    tags=["caselaw"],
    responses={404: {"description": "Not found"}},
)


@router.post("/search", response_model=List[Caselaw], operation_id="search_for_caselaw")
async def search_caselaw_endpoint(
    search: CaselawSearch, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    try:
        result = await caselaw_search(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/section/search",
    response_model=List[CaselawSection],
    operation_id="search_for_caselaw_section",
)
async def search_caselaw_section_endpoint(
    search: CaselawSectionSearch,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    try:
        result = await caselaw_section_search(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/reference/search",
    response_model=List[Caselaw],
    operation_id="search_for_caselaw_by_reference",
)
async def search_caselaw_reference_endpoint(
    search: CaselawReferenceSearch,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    """
    Search for cases that reference a specific case or piece of legislation.

    This endpoint allows you to find all cases that cite a specific case or
    legislation, with optional filtering by court, division, and year range.
    """
    try:
        result = await caselaw_reference_search(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)
