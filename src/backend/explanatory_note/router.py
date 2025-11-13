import traceback
from typing import List

from fastapi import APIRouter, HTTPException

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
    summary="Search explanatory notes by content",
    description="Find explanatory notes by text content across all legislation types.",
)
async def search_explanatory_note_endpoint(search: ExplanatoryNoteSearch):
    try:
        result = await search_explanatory_note(search)
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
    summary="Get explanatory notes for specific legislation",
    description="Retrieve all explanatory notes associated with a particular Act or SI.",
    responses={404: {"description": "Explanatory notes not found for the specified legislation"}},
)
async def get_explanatory_note_by_legislation_endpoint(lookup: ExplanatoryNoteLookup):
    try:
        notes = await get_explanatory_note_by_legislation_id(
            legislation_id=lookup.legislation_id,
            limit=lookup.limit,
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
    summary="Get explanatory note for specific section",
    description="Retrieve the explanatory note that explains a particular section of legislation.",
    responses={404: {"description": "Explanatory note section not found"}},
)
async def get_explanatory_note_by_section_endpoint(lookup: ExplanatoryNoteSectionLookup):
    try:
        note = await get_explanatory_note_by_section(
            legislation_id=lookup.legislation_id,
            section_number=lookup.section_number,
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
