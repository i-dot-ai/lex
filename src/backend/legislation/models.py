from pydantic import BaseModel, Field

from lex.legislation.models import Legislation, LegislationCategory, LegislationType


class LegislationSectionSearch(BaseModel):
    "Search for legislation that is relevant to a specific query. Useful for finding sections of legislation that are relevant to a specific topic."

    query: str = Field(
        description="The natural language query to search for sections of legislation. If empty will return all sections matching filters.",
        examples=["employment termination procedures", "data protection rights", ""],
    )
    legislation_id: str | None = Field(
        default=None,
        description="The legislation_id to search within. Use this if you only want to search within a specific piece of legislation. Accepts both short format (e.g., 'ukpga/1994/13') and full URL format (e.g., 'http://www.legislation.gov.uk/id/ukpga/1994/13'). If not provided, all legislation will be included based on the other filters.",
        examples=["ukpga/1998/42", "ukpga/2018/12"],
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
    offset: int = Field(
        default=0,
        ge=0,
        description="The number of results to skip (for pagination).",
    )
    size: int = Field(
        default=10,
        description="The number of results to return.",
    )
    include_text: bool = Field(
        default=True,
        description="Whether to include full text in results. Set to False for faster performance when only metadata is needed.",
    )


class LegislationActSearch(BaseModel):
    """Search for legislation using semantic hybrid search.

    Searches section content using dense (semantic) + sparse (BM25) embeddings,
    then returns parent legislation ranked by best matching sections.
    """

    query: str = Field(
        description="The search query - can be a concept, question, or keywords.",
        examples=[
            "human rights protections",
            "What are the penalties for tax evasion?",
            "data protection compliance",
        ],
    )
    year_from: int | None = Field(
        default=None,
        description="Starting year filter (optional).",
    )
    year_to: int | None = Field(
        default=None,
        description="Ending year filter (optional).",
    )
    legislation_type: list[LegislationType] | None = Field(
        default=None,
        description="List of legislation types to filter by (optional).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip (pagination).",
    )
    limit: int = Field(
        default=10,
        description="Number of results to return.",
    )
    include_text: bool = Field(
        default=True,
        description="Whether to include full section text in results. Set to False for faster performance when only metadata is needed.",
    )


class LegislationLookup(BaseModel):
    """Lookup legislation by exact type, year, and number.

    This model allows precise retrieval of legislation based on its unique identifiers.

    The legislation_id is composed like this:
    http://www.legislation.gov.uk/id/{legislation_type}/{year}/{number}
    """

    legislation_type: LegislationType = Field(
        description="The specific type of legislation", examples=["ukpga", "uksi"]
    )
    year: int = Field(description="The year the legislation was enacted.", examples=[1998, 2018])
    number: int = Field(description="The number of the legislation.", examples=[42, 12])


class LegislationSectionLookup(BaseModel):
    """Lookup all the sections of a piece of legislation by legislation title."""

    legislation_id: str = Field(
        description="The ID of the legislation to search for.",
        examples=["ukpga/1998/42", "ukpga/2018/12"],
    )
    limit: int = Field(
        default=10,
        description="The number of results to return.",
    )


class LegislationFullTextLookup(BaseModel):
    """Lookup the full text of a legislation document by its ID.

    This model allows retrieval of legislation full text with optional inclusion of schedules.
    """

    legislation_id: str = Field(
        description="The full ID of the legislation document.",
        examples=["ukpga/1998/42", "ukpga/2018/12"],
    )
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


class LegislationSearchResponse(BaseModel):
    """Response model for legislation search with pagination metadata."""

    results: list[dict] = Field(
        description="List of legislation results (may include sections array)"
    )
    total: int = Field(description="Total number of results available")
    offset: int = Field(description="Current offset")
    limit: int = Field(description="Number of results per page")
