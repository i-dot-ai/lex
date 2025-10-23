from typing import Optional

from pydantic import BaseModel, Field

from lex.explanatory_note.models import ExplanatoryNoteSectionType, ExplanatoryNoteType


class ExplanatoryNoteSearch(BaseModel):
    query: str = Field(
        default="",
        description="Natural language query to search explanatory note content. Leave empty to return all notes matching filters.",
    )
    legislation_id: Optional[str] = Field(
        default=None,
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2018/12) to search within. Omit to search across all legislation.",
    )
    note_type: Optional[ExplanatoryNoteType] = Field(
        default=None,
        description="Filter by note type (overview, policy_background, legal_background, extent, provisions, commencement, related_documents). Omit to include all types.",
    )
    section_type: Optional[ExplanatoryNoteSectionType] = Field(
        default=None,
        description="Filter by section type (section, schedule, part). Omit to include all section types.",
    )
    size: int = Field(default=20, description="Maximum number of results to return.")


class ExplanatoryNoteLookup(BaseModel):
    legislation_id: str = Field(
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2018/12) to get explanatory notes for."
    )
    limit: int = Field(
        default=1000,
        description="Maximum number of results to return. High default as explanatory notes are typically comprehensive.",
    )


class ExplanatoryNoteSectionLookup(BaseModel):
    legislation_id: str = Field(
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2018/12) to get explanatory note for."
    )
    section_number: int = Field(
        description="Section number to get the explanatory note for (e.g. 5 for section 5)."
    )
