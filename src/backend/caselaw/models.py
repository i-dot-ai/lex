from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from lex.caselaw.models import Court, CourtDivision


class ReferenceType(str, Enum):
    CASELAW = "caselaw"
    LEGISLATION = "legislation"


class CaselawSearch(BaseModel):
    query: Optional[str] = Field(
        default=None,
        description="Natural language query to search caselaw content. Can be legal issues, questions, or topics. Omit to return results based on filters only.",
    )
    is_semantic_search: bool = Field(
        default=True,
        description="Use semantic search for conceptually related results. Set to false for exact keyword matching.",
    )
    court: Optional[Court] = Field(
        default=None,
        description="Filter by specific courts (UKSC, EWCA, EWHC, etc.). Omit to include all courts.",
    )
    division: Optional[CourtDivision] = Field(
        default=None,
        description="Filter by court division (QBD, CH, COMM, etc.). Omit to include all divisions.",
    )
    year_from: Optional[int] = Field(
        default=None, description="Filter cases from this year onwards. Omit for no year filtering."
    )
    year_to: Optional[int] = Field(
        default=None, description="Filter cases up to this year. Omit for no year filtering."
    )
    size: int = Field(default=20, description="Maximum number of results to return.")


class CaselawSectionSearch(BaseModel):
    query: Optional[str] = Field(
        default=None,
        description="Natural language query to search within case section content (paragraphs, judgments). Omit to return results based on filters only.",
    )
    court: Optional[Court] = Field(
        default=None,
        description="Filter by specific courts (UKSC, EWCA, EWHC, etc.). Omit to include all courts.",
    )
    division: Optional[CourtDivision] = Field(
        default=None,
        description="Filter by court division (QBD, CH, COMM, etc.). Omit to include all divisions.",
    )
    year_from: Optional[int] = Field(
        default=None, description="Filter cases from this year onwards. Omit for no year filtering."
    )
    year_to: Optional[int] = Field(
        default=None, description="Filter cases up to this year. Omit for no year filtering."
    )
    limit: int = Field(default=10, description="Maximum number of results to return.")


class CaselawReferenceSearch(BaseModel):
    reference_id: str = Field(
        description="Full ID of the document to find citing cases for (e.g. https://caselaw.nationalarchives.gov.uk/uksc/2020/17 or http://www.legislation.gov.uk/id/ukpga/2018/12)",
    )
    reference_type: ReferenceType = Field(
        description="Type of document being referenced: 'caselaw' for cases, 'legislation' for Acts/SIs"
    )
    court: Optional[Court] = Field(
        default=None,
        description="Filter citing cases by specific courts (UKSC, EWCA, EWHC, etc.). Omit to include all courts.",
    )
    division: Optional[CourtDivision] = Field(
        default=None,
        description="Filter citing cases by court division (QBD, CH, COMM, etc.). Omit to include all divisions.",
    )
    year_from: Optional[int] = Field(
        default=None,
        description="Filter citing cases from this year onwards. Omit for no year filtering.",
    )
    year_to: Optional[int] = Field(
        default=None, description="Filter citing cases up to this year. Omit for no year filtering."
    )
    size: int = Field(default=20, description="Maximum number of results to return.")
