import traceback
from typing import List

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException

from backend.amendment.models import AmendmentSearch, AmendmentSectionSearch
from backend.amendment.search import search_amendment_sections, search_amendments
from backend.core.dependencies import get_es_client
from lex.amendment.models import Amendment

router = APIRouter(
    prefix="/amendment",
    tags=["amendment"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/search",
    response_model=List[Amendment],
    operation_id="search_amendments",
)
async def search_amendments_endpoint(
    search: AmendmentSearch, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    """
    Search for amendments at the legislation level - either amendments made to or by specific legislation.

    This endpoint allows you to find amendments related to a piece of legislation. You can search
    for amendments that modify the specified legislation (amendments made TO it) or amendments
    that the specified legislation makes to other laws (amendments made BY it).

    Usage patterns:
    - Track changes: Find all amendments made to a specific piece of legislation
    - Legislative impact: See what other legislation a specific Act or SI has amended
    - Amendment history: Understand how legislation has evolved over time
    - Cross-references: Find connections between different pieces of legislation

    Examples:
    - search_amendments({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2018/12", "search_amended": true, "size": 50})  # "Find all amendments made to the Data Protection Act 2018"
    - search_amendments({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2021/30", "search_amended": false, "size": 100})  # "Show me what other legislation the Environment Act 2021 has amended"
    - search_amendments({"legislation_id": "http://www.legislation.gov.uk/id/ukpga/2006/46", "search_amended": true, "size": 200})  # "Get all amendments to the Companies Act 2006"
    - search_amendments({"legislation_id": "http://www.legislation.gov.uk/id/uksi/2021/1074", "search_amended": false, "size": 25})  # "Find what this Statutory Instrument amends"

    Args:
        search: Amendment search parameters including legislation ID, search direction, and result size

    Returns:
        List of Amendment objects related to the specified legislation
    """
    try:
        result = await search_amendments(search, es_client)
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
    response_model=List[Amendment],
    operation_id="search_amendment_sections",
)
async def search_amendment_sections_endpoint(
    search: AmendmentSectionSearch,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    """
    Search for amendments at the provision/section level - either amendments made to or by specific sections.

    This endpoint allows you to find amendments related to a specific section or provision within
    legislation. You can search for amendments that modify the specified provision (amendments made TO it)
    or amendments that the specified provision makes to other laws (amendments made BY it).

    Usage patterns:
    - Section-specific changes: Find all amendments to a particular section
    - Provision impact: See what other provisions a specific section has amended
    - Granular amendment tracking: Understand changes at the section level
    - Cross-provision references: Find connections between specific legislative provisions

    Examples:
    - search_amendment_sections({"provision_id": "http://www.legislation.gov.uk/id/ukpga/2018/12/section/5", "search_amended": true, "size": 20})  # "Find amendments made to section 5 of the Data Protection Act 2018"
    - search_amendment_sections({"provision_id": "http://www.legislation.gov.uk/id/ukpga/2021/30/section/12", "search_amended": false, "size": 15})  # "Show what section 12 of the Environment Act 2021 has amended"
    - search_amendment_sections({"provision_id": "http://www.legislation.gov.uk/id/ukpga/2006/46/section/172", "search_amended": true, "size": 10})  # "Get amendments to section 172 of the Companies Act 2006"
    - search_amendment_sections({"provision_id": "http://www.legislation.gov.uk/id/uksi/2021/1074/regulation/3", "search_amended": false, "size": 5})  # "Find what regulation 3 of this SI amends"

    Args:
        search: Amendment section search parameters including provision ID, search direction, and result size

    Returns:
        List of Amendment objects related to the specified provision
    """
    try:
        result = await search_amendment_sections(search, es_client)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)
