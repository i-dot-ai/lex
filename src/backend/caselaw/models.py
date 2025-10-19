from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from lex.caselaw.models import Caselaw, Court, CourtDivision


class ReferenceType(str, Enum):
    """Type of reference to search for"""

    CASELAW = "caselaw"
    LEGISLATION = "legislation"


class CaselawSearch(BaseModel):
    "Search for caselaw that is relevant to a specific query. Useful for finding caselaw that is relevant to a specific question if this or related topics have been put before the courts."

    query: Optional[str] = Field(
        default=None,
        description="The natural language query to search for caselaw. Often this will be the question on which the case hinges, but it could be more tangential. If not provided, will return results based on filters only.",
    )
    is_semantic_search: bool = Field(
        default=True,
        description="Whether to use semantic search. Unless the user requests a non-semantic search, default to semantic search",
    )
    court: Optional[List[Court]] = Field(default=None, description="Filter by court.")
    division: Optional[List[CourtDivision]] = Field(
        default=None, description="Filter by court division."
    )
    year_from: Optional[int] = Field(
        default=None, description="Filter by cases from this year onwards."
    )
    year_to: Optional[int] = Field(default=None, description="Filter by cases up to this year.")
    offset: int = Field(
        default=0,
        ge=0,
        description="The number of results to skip (for pagination).",
    )
    size: int = Field(default=20, description="Maximum number of results to return.")


class CaselawSectionSearch(BaseModel):
    "Search for caselaw sections that are relevant to a specific query."

    query: Optional[str] = Field(
        default=None,
        description="The query to search for in case names, citations, etc. If not provided, will return results based on filters only.",
    )
    court: Optional[List[Court]] = Field(default=None, description="Filter by court.")
    division: Optional[List[CourtDivision]] = Field(
        default=None, description="Filter by court division."
    )
    year_from: Optional[int] = Field(
        default=None, description="Filter by cases from this year onwards."
    )
    year_to: Optional[int] = Field(default=None, description="Filter by cases up to this year.")
    offset: int = Field(
        default=0,
        ge=0,
        description="The number of results to skip (for pagination).",
    )
    limit: int = Field(default=10, description="Maximum number of results to return.")


class CaselawReferenceSearch(BaseModel):
    "Search for caselaw that references a specific case or legislation."

    reference_id: str = Field(
        description=(
            "The full id of the document you want to find cases that cite. "
            "e.g. https://caselaw.nationalarchives.gov.uk/ukhl/2008/43"
        ),
    )
    reference_type: ReferenceType = Field(
        description="The type of reference to search for (caselaw or legislation)."
    )
    court: Optional[List[Court]] = Field(
        default=None, description="Filter by court of the citing cases."
    )
    division: Optional[List[CourtDivision]] = Field(
        default=None, description="Filter by court division of the citing cases."
    )
    year_from: Optional[int] = Field(
        default=None, description="Filter by citing cases from this year onwards."
    )
    year_to: Optional[int] = Field(
        default=None, description="Filter by citing cases up to this year."
    )
    size: int = Field(default=20, description="Maximum number of results to return.")


class CaselawSearchResponse(BaseModel):
    """Response model for caselaw search with pagination metadata."""

    results: list[Caselaw] = Field(description="List of caselaw results")
    total: int = Field(description="Total number of results available")
    offset: int = Field(description="Current offset")
    size: int = Field(description="Number of results per page")
