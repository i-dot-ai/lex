from pydantic import BaseModel, Field

from lex.legislation.models import (
    Legislation,
    LegislationCategory,
    LegislationType,
)


class LegislationSectionSearch(BaseModel):
    "Search for legislation that is relevant to a specific query. Useful for finding sections of legislation that are relevant to a specific topic."

    query: str = Field(
        description="The natural language query to search for sections of legislation. If empty will return all sections matching filters."
    )
    legislation_id: str | None = Field(
        default=None,
        description="The legislation_id to search within. Use this if you only want to search within a specific piece of legislation. If not provided, all legislation will be included based on the other filters.",
    )
    legislation_category: list[LegislationCategory] | None = Field(
        default=None,
        description="The legislation category to filter by. If not provided, all categories will be included.",
    )
    legislation_type: list[LegislationType] | None = Field(
        default=None,
        description="The legislation type to filter by. If not provided, all types will be included.",
    )
    year_from: int | None = Field(
        default=None,
        description="The starting year for the legislation to filter by. If not provided, no filtering will be applied.",
    )
    year_to: int | None = Field(
        default=None,
        description="The ending year for the legislation to filter by. If not provided, no filtering will be applied.",
    )
    size: int = Field(
        default=10,
        description="The number of results to return.",
    )


class LegislationActSearch(BaseModel):
    """Search for legislation by title with additional filtering options.

    This model provides more control over the title search by allowing:
    - Year range filtering
    - Type filtering
    - Choice of search algorithm
    - Custom result limit
    """

    query: str = Field(
        description="The title of the legislation to search for, if empty will return all matching legislation."
    )
    year_from: int | None = Field(
        default=None,
        description="The starting year for the legislation to filter by. If not provided, no filtering will be applied.",
    )
    year_to: int | None = Field(
        default=None,
        description="The ending year for the legislation to filter by. If not provided, no filtering will be applied.",
    )
    legislation_type: list[LegislationType] | None = Field(
        default=None,
        description="List of legislation types to filter by. If not provided, all subtypes will be included.",
    )
    limit: int = Field(
        default=10,
        description="The number of results to return.",
    )


class LegislationLookup(BaseModel):
    """Lookup legislation by exact type, year, and number.

    This model allows precise retrieval of legislation based on its unique identifiers.

    The legislation_id is composed like this:
    http://www.legislation.gov.uk/id/{legislation_type}/{year}/{number}
    """

    legislation_type: LegislationType = Field(description="The specific type of legislation")
    year: int = Field(description="The year the legislation was enacted.")
    number: int = Field(description="The number of the legislation.")


class LegislationSectionLookup(BaseModel):
    """Lookup all the sections of a piece of legislation by legislation title."""

    legislation_id: str = Field(description="The ID of the legislation to search for.")
    limit: int = Field(
        default=10,
        description="The number of results to return.",
    )


class LegislationFullTextLookup(BaseModel):
    """Lookup the full text of a legislation document by its ID.

    This model allows retrieval of legislation full text with optional inclusion of schedules.
    """

    legislation_id: str = Field(description="The full ID of the legislation document.")
    include_schedules: bool = Field(
        default=False,
        description="Whether to include schedules in the response. If False, only sections are returned. If True, sections are returned first, then schedules. Only request schedules if you are sure you need them.",
    )


class LegislationFullText(BaseModel):
    """Full text of legislation with metadata.

    This model combines the metadata of a legislation document with its
    full text (concatenated from all sections).
    """

    legislation: Legislation = Field(description="The metadata of the legislation document.")
    full_text: str = Field(
        description="The full text of the legislation, concatenated from all sections."
    )
