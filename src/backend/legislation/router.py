import traceback
from typing import List

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException

from backend.core.dependencies import get_es_client
from backend.legislation.models import (
    LegislationActSearch,
    LegislationFullText,
    LegislationFullTextLookup,
    LegislationLookup,
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
    search: LegislationSectionSearch, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    try:
        result = await legislation_section_search(search, es_client)
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
    response_model=List[Legislation],
    operation_id="search_for_legislation_acts",
)
async def search_for_legislation_acts(
    search: LegislationActSearch, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    try:
        result = await legislation_act_search(search, es_client)
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
    lookup: LegislationLookup, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    try:
        result = await legislation_lookup(lookup, es_client)
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
async def get_sections_by_title(
    input: LegislationSectionLookup, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    try:
        sections = await get_legislation_sections(input, es_client)
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
    input: LegislationFullTextLookup, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    try:
        result = await get_legislation_full_text(input, es_client)
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
