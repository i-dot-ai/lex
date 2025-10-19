import traceback
from typing import List

from fastapi import APIRouter, HTTPException

from backend.amendment.models import AmendmentSearch, AmendmentSectionSearch
from backend.amendment.search import search_amendment_sections, search_amendments
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
async def search_amendments_endpoint(search: AmendmentSearch):
    try:
        result = await search_amendments(search)
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
async def search_amendment_sections_endpoint(search: AmendmentSectionSearch):
    try:
        result = await search_amendment_sections(search)
        return result
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)
