import traceback
from typing import List

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException

from backend.core.dependencies import get_es_client
from backend.explanatory_note.models import (
    ExplanatoryNoteLookup,
    ExplanatoryNoteSearch,
    ExplanatoryNoteSectionLookup,
)
from backend.explanatory_note.search import (
    get_explanatory_note_by_legislation_id,
    get_explanatory_note_by_section,
    search_explanatory_note,
)
from lex.explanatory_note.models import ExplanatoryNote

router = APIRouter(
    prefix="/explanatory_note",
    tags=["explanatory_note"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/section/search",
    response_model=List[ExplanatoryNote],
    operation_id="search_explanatory_note",
)
async def search_explanatory_note_endpoint(
    search: ExplanatoryNoteSearch,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    try:
        result = await search_explanatory_note(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.post(
    "/legislation/lookup",
    response_model=List[ExplanatoryNote],
    operation_id="get_explanatory_note_by_legislation",
    responses={404: {"description": "Explanatory notes not found for the specified legislation"}},
)
async def get_explanatory_note_by_legislation_endpoint(
    lookup: ExplanatoryNoteLookup,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    try:
        notes = await get_explanatory_note_by_legislation_id(
            legislation_id=lookup.legislation_id,
            limit=lookup.limit,
            es_client=es_client,
        )
        if not notes:
            raise HTTPException(
                status_code=404,
                detail=f"No explanatory notes found for legislation ID: {lookup.legislation_id}",
            )
        return notes
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
    response_model=ExplanatoryNote,
    operation_id="get_explanatory_note_by_section",
    responses={404: {"description": "Explanatory note section not found"}},
)
async def get_explanatory_note_by_section_endpoint(
    lookup: ExplanatoryNoteSectionLookup,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    try:
        note = await get_explanatory_note_by_section(
            legislation_id=lookup.legislation_id,
            section_number=lookup.section_number,
            es_client=es_client,
        )
        if note is None:
            raise HTTPException(
                status_code=404,
                detail=f"No explanatory note found for legislation ID: {lookup.legislation_id} and section number: {lookup.section_number}",
            )
        return note
    except HTTPException:
        raise
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)
