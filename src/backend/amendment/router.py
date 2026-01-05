from typing import List

from fastapi import APIRouter

from backend.amendment.models import AmendmentSearch, AmendmentSectionSearch
from backend.amendment.search import search_amendment_sections, search_amendments
from backend.core.error_handling import handle_errors
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
    summary="Search legislative amendments",
    description="Find amendments to Acts and SIs by content, title, or affected legislation.",
)
@handle_errors
async def search_amendments_endpoint(search: AmendmentSearch):
    return await search_amendments(search)


@router.post(
    "/section/search",
    response_model=List[Amendment],
    operation_id="search_amendment_sections",
    summary="Search within amendment sections",
    description="Find text within specific sections of legislative amendments.",
)
@handle_errors
async def search_amendment_sections_endpoint(search: AmendmentSectionSearch):
    return await search_amendment_sections(search)
