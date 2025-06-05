from typing import List, Optional

from pydantic import BaseModel, Field

from lex.explanatory_note.models import ExplanatoryNoteSectionType, ExplanatoryNoteType


class ExplanatoryNoteSearch(BaseModel):
    """Search for explanatory notes that match the given query."""

    query: str = Field(
        default="",
        description="The natural language query to search for explanatory notes. If empty, will return all notes matching the filters.",
    )
    legislation_id: Optional[str] = Field(
        default=None,
        description="Filter by legislation ID to search within a specific piece of legislation. If not provided, all legislation will be included.",
    )
    note_type: Optional[List[ExplanatoryNoteType]] = Field(
        default=None,
        description="Filter by note type (overview, policy_background, legal_background, extent, provisions, commencement, related_documents).",
    )
    section_type: Optional[List[ExplanatoryNoteSectionType]] = Field(
        default=None,
        description="Filter by section type (section, schedule, part).",
    )
    size: int = Field(default=20, description="Maximum number of results to return.")


class ExplanatoryNoteLookup(BaseModel):
    """Lookup explanatory notes for a specific legislation by ID."""

    legislation_id: str = Field(
        description="The ID of the legislation to look up explanatory notes for."
    )
    limit: int = Field(default=1000, description="Maximum number of results to return.")


class ExplanatoryNoteSectionLookup(BaseModel):
    """Lookup a specific explanatory note section by legislation ID and section number."""

    legislation_id: str = Field(
        description="The ID of the legislation to look up an explanatory note for."
    )
    section_number: int = Field(
        description="The section number to look up an explanatory note for."
    )
