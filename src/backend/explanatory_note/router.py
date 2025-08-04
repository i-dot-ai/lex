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
    """
    Search for explanatory notes that match a natural language query.

    This endpoint searches through explanatory notes that accompany legislation to provide
    context, background, and explanation of the legislative provisions. Use this when you
    need to understand the policy intent, background, or practical implications of legislation.

    Usage patterns:
    - Topic-based search: Find explanatory notes about specific subjects
    - Policy context: Understand the background and rationale behind legislation
    - Filtered search: Focus on specific types of notes or legislation
    - Browse discovery: Use empty query with filters to explore explanatory content

    Examples:
    - search_explanatory_note({"query": "data protection impact assessment", "size": 15})  # "Find explanatory notes about data protection impact assessments"
    - search_explanatory_note({"query": "climate change policy", "note_type": ["policy_background"], "size": 10})  # "Show policy background notes about climate change"
    - search_explanatory_note({"query": "small business exemption", "legislation_id": "http://www.legislation.gov.uk/id/ukpga/2018/12", "size": 20})  # "Find explanatory notes about small business exemptions in the Data Protection Act 2018"
    - search_explanatory_note({"query": "", "note_type": ["commencement"], "size": 25})  # "Browse all commencement explanatory notes"
    - search_explanatory_note({"query": "territorial extent", "section_type": ["section"], "size": 30})  # "Find section-level explanatory notes about territorial extent"

    Args:
        search: Search parameters including query, legislation ID, note type, section type, and result size

    Returns:
        List of ExplanatoryNote objects matching the search criteria, ranked by relevance
    """
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
    """
    Retrieve all explanatory notes for a specific piece of legislation by its ID.

    This endpoint returns all explanatory notes associated with a particular Act or
    Statutory Instrument. Use this when you need comprehensive explanatory material
    for specific legislation, including policy background, legal context, and implementation details.

    Usage patterns:
    - Complete explanatory context: Get all explanatory material for specific legislation
    - Policy research: Understand the full background and rationale behind legislation
    - Implementation guidance: Access detailed explanations of how legislation works
    - Legislative analysis: Get comprehensive explanatory content for legal analysis

    Examples:
    - get_explanatory_note_by_legislation({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2018/12", "limit": 100})  # "Get all explanatory notes for the Data Protection Act 2018"
    - get_explanatory_note_by_legislation({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2021/30", "limit": 50})  # "Show me all explanatory notes for the Environment Act 2021"
    - get_explanatory_note_by_legislation({"legislation_id": "http://www.legislation.gov.uk/id/uksi/2021/1074", "limit": 25})  # "Retrieve explanatory notes for this Statutory Instrument"
    - get_explanatory_note_by_legislation({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2006/46", "limit": 200})  # "Get comprehensive explanatory notes for the Companies Act 2006"

    Args:
        lookup: Legislation ID and optional limit for number of explanatory notes to return

    Returns:
        List of ExplanatoryNote objects for the specified legislation

    Raises:
        404: If no explanatory notes found for the specified legislation ID
    """
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
    """
    Retrieve the explanatory note for a specific section of legislation.

    This endpoint returns the explanatory note that corresponds to a particular section
    number within a piece of legislation. Use this when you need targeted explanation
    of what a specific section does, why it was included, and how it should be interpreted.

    Usage patterns:
    - Section-specific explanation: Get targeted explanation for a particular provision
    - Provision analysis: Understand the purpose and context of specific sections
    - Implementation guidance: Access detailed explanation of how specific sections work
    - Legislative interpretation: Get authoritative explanation of section meaning

    Examples:
    - get_explanatory_note_by_section({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2018/12", "section_number": 5})  # "Explain what section 5 of the Data Protection Act 2018 does"
    - get_explanatory_note_by_section({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2006/46", "section_number": 172})  # "Get the explanatory note for section 172 of the Companies Act 2006"
    - get_explanatory_note_by_section({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2021/30", "section_number": 1})  # "What does section 1 of the Environment Act 2021 cover?"
    - get_explanatory_note_by_section({"legislation_id": "http://www.legislation.gov.uk/id/uksi/2021/1074", "section_number": 3})  # "Explain section 3 of this Statutory Instrument"

    Args:
        lookup: Legislation ID and specific section number to look up

    Returns:
        Single ExplanatoryNote object explaining the specified section

    Raises:
        404: If no explanatory note found for the specified legislation ID and section number
    """
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
