from typing import List

from fastapi import APIRouter, HTTPException

from backend.core.error_handling import handle_errors
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
@handle_errors
async def search_explanatory_note_endpoint(search: ExplanatoryNoteSearch):
    return await search_explanatory_note(search)


@router.post(
    "/legislation/lookup",
    response_model=List[ExplanatoryNote],
    operation_id="get_explanatory_note_by_legislation",
    summary="Get explanatory notes for specific legislation",
    description="Retrieve all explanatory notes associated with a particular Act or SI.",
    responses={404: {"description": "Explanatory notes not found for the specified legislation"}},
)
@handle_errors
async def get_explanatory_note_by_legislation_endpoint(lookup: ExplanatoryNoteLookup):
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


@router.post(
    "/section/lookup",
    response_model=ExplanatoryNote,
    operation_id="get_explanatory_note_by_section",
    summary="Get explanatory note for specific section",
    description="Retrieve the explanatory note that explains a particular section of legislation.",
    responses={404: {"description": "Explanatory note section not found"}},
)
@handle_errors
async def get_explanatory_note_by_section_endpoint(lookup: ExplanatoryNoteSectionLookup):
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
