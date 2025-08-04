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
    """
    Search for caselaw that is relevant to a specific query using semantic or keyword search.

    This endpoint searches through court cases to find relevant legal precedents and decisions.
    Use this when you need to find cases that deal with specific legal issues, topics, or
    questions that may have been put before the courts.

    Usage patterns:
    - Topic-based search: Find cases dealing with specific legal issues
    - Court filtering: Focus on specific courts or divisions
    - Time-bounded search: Limit results to specific date ranges
    - Semantic search: Find conceptually related cases (default)
    - Keyword search: Find exact term matches

    Examples:
    - search_for_caselaw({"query": "contract breach remedies", "size": 20})  # "Find cases about contract breach remedies"
    - search_for_caselaw({"query": "data protection privacy", "court": ["UKSC"], "size": 10})  # "Show me Supreme Court cases about data protection"
    - search_for_caselaw({"query": "negligence duty of care", "year_from": 2020, "year_to": 2024})  # "Find recent negligence cases from 2020-2024"
    - search_for_caselaw({"query": "employment discrimination", "division": ["QBD"], "size": 15})  # "Search Queen's Bench Division for employment discrimination cases"
    - search_for_caselaw({"query": "human rights", "is_semantic_search": false, "size": 25})  # "Find cases with exact 'human rights' keywords"

    Args:
        search: Search parameters including query, court filters, date range, and search type

    Returns:
        List of Caselaw objects matching the search criteria, ranked by relevance
    """
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
    """
    Search for specific sections within caselaw documents that match a query.

    This endpoint searches within the actual content of court judgments to find specific
    paragraphs, sections, or passages that are relevant to your query. Use this when you
    need to find particular parts of judgments rather than entire cases.

    Usage patterns:
    - Granular search: Find specific passages within judgments
    - Quote finding: Locate particular judicial statements or reasoning
    - Issue-specific search: Find sections dealing with narrow legal points
    - Citation context: Find how specific legal principles are discussed

    Examples:
    - search_caselaw_section({"query": "reasonable foreseeability test", "limit": 15})  # "Find sections discussing the reasonable foreseeability test"
    - search_caselaw_section({"query": "breach of contract damages", "court": ["COMM"], "limit": 10})  # "Find Commercial Court sections about contract breach damages"
    - search_caselaw_section({"query": "proportionality assessment", "year_from": 2018, "limit": 20})  # "Show sections about proportionality from 2018 onwards"
    - search_caselaw_section({"query": "", "division": ["CH"], "year_from": 2023, "limit": 30})  # "Browse recent Chancery Division case sections"

    Args:
        search: Search parameters including query, court filters, date range, and result limit

    Returns:
        List of CaselawSection objects with matching content, ranked by relevance
    """
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
    Search for cases that reference or cite a specific case or piece of legislation.

    This endpoint allows you to find all cases that cite a specific case or legislation,
    with optional filtering by court, division, and year range. Use this for legal research
    to understand how precedents have been applied or how legislation has been interpreted.

    Usage patterns:
    - Precedent tracking: Find cases that follow or distinguish a precedent
    - Legislative interpretation: See how courts have interpreted specific legislation
    - Citation analysis: Understand the influence of landmark cases
    - Judicial consideration: Find cases that mention specific legal authorities

    Examples:
    - search_caselaw_reference({"reference_id": "https://caselaw.nationalarchives.gov.uk/uksc/2020/17", "reference_type": "caselaw", "size": 20})  # "Find all cases that cite this Supreme Court judgment"
    - search_caselaw_reference({"reference_id": "http://www.legislation.gov.uk/id/ukpga/2018/12", "reference_type": "legislation", "size": 15})  # "Find cases that reference the Data Protection Act 2018"
    - search_caselaw_reference({"reference_id": "https://caselaw.nationalarchives.gov.uk/ewca/civ/2021/123", "reference_type": "caselaw", "court": ["EWCA"], "size": 10})  # "Find Court of Appeal cases citing this specific judgment"
    - search_caselaw_reference({"reference_id": "http://www.legislation.gov.uk/id/ukpga/2006/46", "reference_type": "legislation", "year_from": 2020, "size": 25})  # "Find recent cases referencing the Companies Act 2006"

    Args:
        search: Reference search parameters including the document ID, reference type, and filters

    Returns:
        List of Caselaw objects that cite the specified reference, ranked by relevance
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
