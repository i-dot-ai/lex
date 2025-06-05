from enum import Enum

from pydantic import Field

from lex.core.models import EmbeddableModel


class ExplanatoryNoteType(str, Enum):
    OVERVIEW = "overview"
    POLICY_BACKGROUND = "policy_background"
    LEGAL_BACKGROUND = "legal_background"
    EXTENT = "extent"
    PROVISIONS = "provisions"
    COMMENCEMENT = "commencement"


class ExplanatoryNoteSectionType(str, Enum):
    SECTION = "section"
    SCHEDULE = "schedule"
    PART = "part"


class ExplanatoryNote(EmbeddableModel):
    id: str
    legislation_id: str
    note_type: ExplanatoryNoteType | None = Field(
        default=None,
        description="The type of explanatory note",
    )
    route: list[str]
    section_type: ExplanatoryNoteSectionType | None = Field(default=None)
    section_number: int | None = Field(default=None)
    order: int

    @property
    def content(self):
        res = ""
        for i, field in enumerate(self.route):
            res += f"{'#' * (i + 2)} {field}\n"
        res += f"{self.text}"
        return res
