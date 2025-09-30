import traceback
from typing import List, Optional

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query

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
from lex.legislation.models import (
    Legislation,
    LegislationCategory,
    LegislationSection,
    LegislationType,
)

router = APIRouter(
    prefix="/legislation",
    tags=["legislation"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/section/search",
    response_model=List[LegislationSection],
    operation_id="search_for_legislation_sections",
)
async def search_for_legislation_sections(
    es_client: AsyncElasticsearch = Depends(get_es_client),
    query: str = Query(
        ..., description="Natural language query to search within legislation sections"
    ),
    legislation_id: Optional[str] = Query(None, description="Full legislation ID to search within"),
    legislation_category: Optional[LegislationCategory] = Query(
        None, description="Filter by legislation category"
    ),
    legislation_type: Optional[LegislationType] = Query(
        None, description="Filter by legislation type"
    ),
    year_from: Optional[int] = Query(None, description="Filter legislation from this year onwards"),
    year_to: Optional[int] = Query(None, description="Filter legislation up to this year"),
    size: int = Query(10, description="Maximum number of results to return"),
):
    """
    Search for specific sections within legislation documents using natural language queries.

    This endpoint searches within the actual content of legislation sections (not just titles)
    to find relevant provisions. Useful for finding specific clauses, definitions, or requirements
    within legislation that relate to your query.

    Usage patterns:
    - Topic-based search: Find sections that deal with specific subjects
    - Within specific legislation: Search only within a particular Act or Instrument
    - Filtered search: Combine queries with year ranges, types, and categories
    - Broad discovery: Use empty query with filters to browse sections

    Examples:
    - search_for_legislation_sections(query="data protection", size=20)  # "What sections of legislation deal with data protection?"
    - search_for_legislation_sections(query="penalty", legislation_id="http://www.legislation.gov.uk/id/ukpga/2006/46", size=10)  # "Find provisions about penalties in the Companies Act 2006"
    - search_for_legislation_sections(query="tax relief", year_from=2020, year_to=2024, legislation_type="ukpga")  # "Show me all sections about tax relief from 2020-2024"
    - search_for_legislation_sections(query="liability", legislation_type="uksi", size=50)  # "Search for liability clauses in all statutory instruments"

    Args:
        query: Natural language query to search within legislation sections
        legislation_id: Full legislation ID to search within specific legislation
        legislation_category: Filter by legislation category (primary/secondary)
        legislation_type: Filter by legislation type (ukpga, uksi, asp, etc.)
        year_from: Filter legislation from this year onwards
        year_to: Filter legislation up to this year
        size: Maximum number of results to return

    Returns:
        List of LegislationSection objects with matching content, ranked by relevance
    """
    try:
        search = LegislationSectionSearch(
            query=query,
            legislation_id=legislation_id,
            legislation_category=legislation_category,
            legislation_type=legislation_type,
            year_from=year_from,
            year_to=year_to,
            size=size,
        )
        result = await legislation_section_search(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.get(
    "/search",
    response_model=List[Legislation],
    operation_id="search_for_legislation_acts",
)
async def search_for_legislation_acts(
    es_client: AsyncElasticsearch = Depends(get_es_client),
    query: Optional[str] = Query(..., description="Search query for legislation titles and short titles"),
    year_from: Optional[int] = Query(None, description="Filter legislation from this year onwards"),
    year_to: Optional[int] = Query(None, description="Filter legislation up to this year"),
    legislation_type: Optional[LegislationType] = Query(
        None, description="Filter by legislation type"
    ),
    limit: int = Query(10, description="Maximum number of results to return"),
):
    """
    Search for legislation documents by title and metadata with advanced filtering options.

    This endpoint searches legislation titles, short titles, and metadata to find relevant Acts,
    Statutory Instruments, and other legislation. Use this when you need to find specific
    legislation documents rather than searching within their content.

    Usage patterns:
    - Title search: Find legislation by name or partial title
    - Year filtering: Limit results to specific time periods
    - Type filtering: Focus on specific legislation types (Acts, SIs, etc.)
    - Browse all: Use empty query with filters to discover legislation

    Examples:
    - search_for_legislation_acts(query="Companies Act", limit=5)  # "Find the Companies Act"
    - search_for_legislation_acts(query="climate change", year_from=2020, limit=10)  # "What legislation was passed about climate change?"
    - search_for_legislation_acts(legislation_type="ukpga", year_from=2020, year_to=2023, limit=20)  # "Show me all Acts from 2020-2023"
    - search_for_legislation_acts(query="tax", legislation_type="uksi", limit=15)  # "List all Statutory Instruments about tax"

    Args:
        query: Search query for legislation titles and short titles
        year_from: Filter legislation from this year onwards
        year_to: Filter legislation up to this year
        legislation_type: Filter by legislation type
        limit: Maximum number of results to return

    Returns:
        List of Legislation objects matching the search criteria, ranked by relevance
    """
    try:
        search = LegislationActSearch(
            query=query,
            year_from=year_from,
            year_to=year_to,
            legislation_type=legislation_type,
            limit=limit,
        )
        result = await legislation_act_search(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@router.get(
    "/lookup",
    response_model=Legislation,
    operation_id="lookup_legislation",
    responses={404: {"description": "Legislation not found"}},
)
async def lookup_legislation_endpoint(
    es_client: AsyncElasticsearch = Depends(get_es_client),
    legislation_type: LegislationType = Query(
        ..., description="Legislation type (ukpga, uksi, asp, etc.)"
    ),
    year: int = Query(..., description="Year the legislation was enacted"),
    number: int = Query(..., description="Legislation number"),
):
    """
    Retrieve a specific piece of legislation by its exact type, year, and number.

    This endpoint provides precise lookup of legislation when you know the exact citation.
    Use this when you have the specific reference (e.g., "2006 c. 46" for Companies Act 2006)
    and need the complete metadata for that legislation.

    The legislation ID format follows:
    http://www.legislation.gov.uk/id/{legislation_type}/{year}/{number}

    Usage patterns:
    - Exact citation lookup: When you have the precise legislative reference
    - Verification: Confirm a piece of legislation exists with specific details
    - Metadata retrieval: Get complete information about a known piece of legislation

    Examples:
    - lookup_legislation(legislation_type="ukpga", year=2006, number=46)  # "Get the Companies Act 2006 (c. 46)"
    - lookup_legislation(legislation_type="uksi", year=2021, number=1074)  # "Retrieve SI 2021/1074 details"
    - lookup_legislation(legislation_type="asp", year=2020, number=1)  # "Lookup the specific Scottish Act from a legal citation"
    - lookup_legislation(legislation_type="wsi", year=2021, number=1428)  # "Get Welsh SI 2021/1428 metadata"

    Args:
        legislation_type: Legislation type (ukpga, uksi, asp, etc.)
        year: Year the legislation was enacted
        number: Legislation number

    Returns:
        Single Legislation object with complete metadata

    Raises:
        404: If no legislation found with the specified type, year, and number
    """
    try:
        lookup = LegislationLookup(
            legislation_type=legislation_type,
            year=year,
            number=number,
        )
        result = await legislation_lookup(lookup, es_client)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Legislation not found: {legislation_type.value} {year} No. {number}",
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
    "/section/lookup",
    response_model=List[LegislationSection],
    operation_id="get_legislation_sections",
    responses={404: {"description": "No sections found for the specified legislation title"}},
)
async def get_sections_by_id(
    es_client: AsyncElasticsearch = Depends(get_es_client),
    legislation_id: str = Query(..., description="Full legislation ID"),
    limit: int = Query(10, description="Maximum number of sections to return"),
):
    """
    Retrieve all sections from a specific piece of legislation by its ID.

    This endpoint returns all the individual sections/provisions that make up a piece of
    legislation. Use this when you need to see the complete structure and content of
    a specific Act or Statutory Instrument, broken down by sections.

    Usage patterns:
    - Complete legislation breakdown: Get all sections of a specific Act or SI
    - Structure analysis: Understand how legislation is organized
    - Bulk section retrieval: Access all provisions at once for analysis
    - Reference material: Get the full sectional content for legal research

    Examples:
    - get_legislation_sections(legislation_id="http://www.legislation.gov.uk/id/ukpga/2006/46", limit=500)  # "Show me all sections of the Companies Act 2006"
    - get_legislation_sections(legislation_id="http://www.legislation.gov.uk/id/uksi/2021/1074", limit=50)  # "Get the complete breakdown of this Statutory Instrument"
    - get_legislation_sections(legislation_id="http://www.legislation.gov.uk/id/ukpga/2018/12", limit=200)  # "I need all provisions from the Data Protection Act 2018"
    - get_legislation_sections(legislation_id="http://www.legislation.gov.uk/id/ukpga/1974/37", limit=100)  # "List every section in the Health and Safety at Work Act 1974"

    Args:
        legislation_id: Full legislation ID
        limit: Maximum number of sections to return

    Returns:
        List of LegislationSection objects for the specified legislation, ordered by section number

    Raises:
        404: If no sections found for the specified legislation ID
    """
    try:
        input = LegislationSectionLookup(
            legislation_id=legislation_id,
            limit=limit,
        )
        sections = await get_legislation_sections(input, es_client)
        if not sections:
            raise HTTPException(
                status_code=404, detail=f"No sections found for legislation ID: {legislation_id}"
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


@router.get(
    "/text",
    response_model=LegislationFullText,
    operation_id="get_legislation_full_text",
    responses={404: {"description": "Legislation not found"}},
)
async def get_full_text_by_id(
    es_client: AsyncElasticsearch = Depends(get_es_client),
    legislation_id: str = Query(..., description="Full legislation ID"),
    include_schedules: bool = Query(False, description="Include schedules in the full text"),
):
    """
    Retrieve the complete full text of a legislation document as a single concatenated string.

    This endpoint returns the entire text content of a piece of legislation, with all sections
    combined into one continuous text. Optionally includes schedules. Use this when you need
    the complete text for analysis, processing, or when working with the legislation as a whole document.

    Usage patterns:
    - Full document analysis: When you need to analyze the complete legislation text
    - Text processing: For NLP, summarization, or other text analysis tasks
    - Complete reading: When you want the full legislation in readable format
    - Research: For comprehensive legal research requiring the entire document

    Examples:
    - get_legislation_full_text(legislation_id="http://www.legislation.gov.uk/id/ukpga/2006/46", include_schedules=False)  # "Give me the complete text of the Companies Act 2006"
    - get_legislation_full_text(legislation_id="http://www.legislation.gov.uk/id/ukpga/2018/12", include_schedules=True)  # "I need the full Data Protection Act 2018 with schedules for analysis"
    - get_legislation_full_text(legislation_id="http://www.legislation.gov.uk/id/uksi/2021/1074", include_schedules=False)  # "Get the entire text of this SI for review"
    - get_legislation_full_text(legislation_id="http://www.legislation.gov.uk/id/wsi/2021/1428", include_schedules=True)  # "Provide the complete Welsh SI with schedules for summary"

    Args:
        legislation_id: Full legislation ID
        include_schedules: Whether to include schedules in the full text

    Returns:
        LegislationFullText object containing metadata and complete concatenated text

    Raises:
        404: If legislation not found with the specified ID

    Note:
        Only request schedules if you specifically need them, as they can significantly increase response size
    """
    try:
        input = LegislationFullTextLookup(
            legislation_id=legislation_id,
            include_schedules=include_schedules,
        )
        result = await get_legislation_full_text(input, es_client)
        if not result:
            raise HTTPException(status_code=404, detail=f"Legislation not found: {legislation_id}")
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
