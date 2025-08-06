from pydantic import BaseModel, Field

from lex.legislation.models import (
    Legislation,
    LegislationCategory,
    LegislationType,
)


class LegislationSectionSearch(BaseModel):
    query: str = Field(
        description="Natural language query to search within legislation section content. Leave empty to return all sections matching filters."
    )
    legislation_id: str | None = Field(
        default=None,
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2006/46) to search within. Omit to search across all legislation.",
    )
    legislation_category: LegislationCategory | None = Field(
        default=None,
        description="Filter by legislation category (primary/secondary). Omit to include all categories.",
    )
    legislation_type: LegislationType | None = Field(
        default=None,
        description="Filter by legislation type (ukpga, uksi, asp, etc.). Omit to include all types.",
    )
    year_from: int | None = Field(
        default=None,
        description="Filter legislation from this year onwards. Omit for no year filtering.",
    )
    year_to: int | None = Field(
        default=None,
        description="Filter legislation up to this year. Omit for no year filtering.",
    )
    size: int = Field(
        default=10,
        description="Maximum number of results to return.",
    )


class LegislationActSearch(BaseModel):
    query: str = Field(
        description="Search query for legislation titles and short titles. Leave empty to return all legislation matching filters."
    )
    year_from: int | None = Field(
        default=None,
        description="Filter legislation from this year onwards. Omit for no year filtering.",
    )
    year_to: int | None = Field(
        default=None,
        description="Filter legislation up to this year. Omit for no year filtering.",
    )
    legislation_type: LegislationType | None = Field(
        default=None,
        description="Filter by legislation type (ukpga, uksi, asp, etc.). Omit to include all types.",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return.",
    )


class LegislationLookup(BaseModel):
    legislation_type: LegislationType = Field(
        description="Legislation type (ukpga, uksi, asp, etc.)"
    )
    year: int = Field(description="Year the legislation was enacted")
    number: int = Field(description="Legislation number (e.g. 46 for Companies Act 2006 c. 46)")


class LegislationSectionLookup(BaseModel):
    legislation_id: str = Field(
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2006/46)"
    )
    limit: int = Field(
        default=10,
        description="Maximum number of sections to return.",
    )


class LegislationFullTextLookup(BaseModel):
    legislation_id: str = Field(
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2006/46)"
    )
    include_schedules: bool = Field(
        default=False,
        description="Include schedules in the full text. Warning: schedules can significantly increase response size.",
    )


class LegislationFullText(BaseModel):
    legislation: Legislation = Field(description="Legislation metadata and details")
    full_text: str = Field(
        description="Complete legislation text concatenated from all sections and optionally schedules"
    )
