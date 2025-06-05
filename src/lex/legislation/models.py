from datetime import date
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from lex.core.models import EmbeddableModel, LexModel


class LegislationCategory(str, Enum):
    """High-level categorization of legislation types.

    This enum represents the three main categories of legislation:
    - PRIMARY: Main acts of parliament and assemblies (e.g., UK Public General Acts, Scottish Parliament Acts)
    - SECONDARY: Statutory instruments and rules (e.g., UK Statutory Instruments, Scottish Statutory Instruments)
    - EUROPEAN: EU-derived legislation (e.g., EU Decisions, Directives, Regulations)
    - EUROPEAN_RETAINED: EU-derived legislation that has been retained in UK law (e.g., EU retained legislation)
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EUROPEAN = "european"
    EUROPEAN_RETAINED = "euretained"


class LegislationType(str, Enum):
    """Specific types of legislation.

    This enum represents all possible legislation subtypes, mapped to their full names:
    - UKPGA: UK Public General Acts
    - ASP: Acts of the Scottish Parliament
    - ASC: Acts of Senedd Cymru
    - ANAW: Acts of the National Assembly for Wales
    - WSI: Wales Statutory Instruments
    - UKSI: UK Statutory Instruments
    - SSI: Scottish Statutory Instruments
    - UKCM: Church Measures
    - NISR: Northern Ireland Statutory Rules
    - NIA: Acts of the Northern Ireland Assembly
    - EUDN: Decisions originating from the EU
    - EUDR: Directives originating from the EU
    - EUR: Regulations originating from the EU
    - UKLA: UK Local Acts
    - UKPPA: UK Private and Personal Acts
    - APNI: Acts of the Northern Ireland Parliament
    - GBLA: Local Acts of the Parliament of Great Britain
    - AOSP: Acts of the Old Scottish Parliament
    - AEP: Acts of the English Parliament
    - APGB: Acts of the Parliament of Great Britain
    - MWA: Measures of the Welsh Assembly
    - AIP: Acts of the Old Irish Parliament
    - MNIA: Measures of the Northern Ireland Assembly
    - NISRO: Northern Ireland Statutory Rules and Orders
    - NISI: Northern Ireland Orders in Council
    - UKSRO: UK Statutory Rules and Orders
    - UKMO: UK Ministerial Orders
    - UKCI: Church Instruments
    """

    UKPGA = "ukpga"
    ASP = "asp"
    ASC = "asc"
    ANAW = "anaw"
    WSI = "wsi"
    UKSI = "uksi"
    SSI = "ssi"
    UKCM = "ukcm"
    NISR = "nisr"
    NIA = "nia"
    EUDN = "eudn"
    EUDR = "eudr"
    EUR = "eur"
    UKLA = "ukla"
    UKPPA = "ukppa"
    APNI = "apni"
    GBLA = "gbla"
    AOSP = "aosp"
    AEP = "aep"
    APGB = "apgb"
    MWA = "mwa"
    AIP = "aip"
    MNIA = "mnia"
    NISRO = "nisro"
    NISI = "nisi"
    UKSRO = "uksro"
    UKMO = "ukmo"
    UKCI = "ukci"


class ReferenceType(str, Enum):
    """Represents the type of reference found in legislation."""

    CROSS_REFERENCE = "cross_reference"
    IMPLEMENTATION = "implementation"
    MODIFICATION = "modification"
    INTERPRETATION = "interpretation"
    OTHER = "other"


class ReferenceLevel(str, Enum):
    """Hierarchical level of legislative reference."""

    SELF = "self"
    ACT = "act"
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"


class GeographicalExtent(str, Enum):
    """Represents the valid geographical extent of legislation."""

    E = "England"
    W = "Wales"
    S = "Scotland"
    NI = "Northern Ireland"
    UK = "United Kingdom"
    NONE = ""


class ProvisionType(str, Enum):
    """Represents the type of provision."""

    SECTION = "section"
    SCHEDULE = "schedule"


class IdReference(BaseModel):
    """A reference to another legislative element from and to an ID."""

    source_id: str
    target_id: str
    type: str
    context: Optional[str] = None


class CommentaryCitation(BaseModel):
    """A reference to a commentary citation."""

    id: str
    uri: str
    type: str
    context: Optional[str] = None
    section_ref: Optional[str] = None
    citation_ref: Optional[str] = None
    citation_type: Optional[str] = None  # primary or sub_reference


class FreeTextReference(BaseModel):
    """A reference to another legislative element by free text."""

    source_id: str
    context: str
    act: Optional[str] = None
    section: Optional[str] = None
    type: Optional[str] = None

    @property
    def target_label(self) -> str:
        """Return the target label of the reference."""
        if self.act and self.section:
            return f"{self.act}, section {self.section}"
        elif self.act:
            return self.act
        elif self.section:
            return f"section {self.section}"
        return "Unknown"

    def __repr__(self) -> str:
        if self.act and self.section:
            return f"FreeTextReference(act='{self.act}', section='{self.section}')"
        elif self.act:
            return f"FreeTextReference(act='{self.act}')"
        elif self.section:
            return f"FreeTextReference(section='{self.section}')"
        return "FreeTextReference()"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FreeTextReference):
            return False
        return str(self.section) == str(other.section) and self.act == other.act

    def __hash__(self) -> int:
        return hash((self.act, str(self.section) if self.section else None))

    @model_validator(mode="after")
    def check_act_or_section(self):
        has_act = self.act is not None and self.act != ""
        has_section = self.section is not None and self.section != ""
        if not has_act and not has_section:
            raise ValueError("Either act or section must be provided")
        return self


class LegislativeText(EmbeddableModel):
    """Base class for legislative text elements."""

    id: str
    uri: str
    references: List[FreeTextReference] = Field(default_factory=list)
    commentary_refs: List[str] = Field(default_factory=list)

    def add_reference(self, reference: FreeTextReference) -> None:
        """Add a reference to the legislative text."""
        self.references.append(reference)

    @property
    def num_references(self) -> int:
        """Return the number of free-text references in the legislative text."""
        return len(self.references)

    @property
    def num_commentary_refs(self) -> int:
        """Return the number of commentary references in the legislative text."""
        return len(self.commentary_refs)


class Paragraph(LegislativeText):
    """Represents a paragraph within a section."""

    number: str
    legislation_id: str
    paragraph_id: Optional[str] = None


class Provision(LegislativeText):
    """Represents the generic concept of a provision within legislation."""

    number: str
    title: str = Field(default_factory=str)
    extent: List[GeographicalExtent] = Field(default_factory=list)
    legislation_id: str
    paragraphs: List[Paragraph] = Field(default_factory=list)

    def add_paragraph(self, paragraph: Paragraph) -> None:
        """Add a paragraph to the section."""
        self.paragraphs.append(paragraph)

    @property
    def total_references(self) -> int:
        """Return the total number of references in the section."""
        return self.num_references + sum(paragraph.num_references for paragraph in self.paragraphs)

    @property
    def total_commentary_refs(self) -> int:
        """Return the total number of commentary references in the section."""
        return self.num_commentary_refs + sum(
            paragraph.num_commentary_refs for paragraph in self.paragraphs
        )

    @property
    def all_references(self) -> List[FreeTextReference]:
        """Return all references in the section and its child paragraphs."""
        references = []
        for paragraph in self.paragraphs:
            references.extend(paragraph.references)
        return self.references + references

    @property
    def all_commentary_refs(self) -> List[str]:
        """Return all commentary_refs in the section and its child paragraphs."""
        commentary_refs = []
        for paragraph in self.paragraphs:
            commentary_refs.extend(paragraph.commentary_refs)
        return self.commentary_refs + commentary_refs

    def get_all_text(self) -> str:
        """Return all text in the section and its child paragraphs."""
        text = self.title + "\n"
        for paragraph in self.paragraphs:
            text += paragraph.paragraph_id + ": " + paragraph.text + "\n"
        return text


class Section(Provision):
    """Represents a UK section/EU article containing paragraphs."""

    provision_type: ProvisionType = ProvisionType.SECTION

    pass


class Schedule(Provision):
    """Represents a schedule within a piece of legislation."""

    provision_type: ProvisionType = ProvisionType.SCHEDULE

    pass


class Commentary(BaseModel):
    """Represents a commentary within a piece of legislation."""

    id: str
    type: str
    citations: List[CommentaryCitation] = Field(default_factory=list)
    text: str


class Legislation(LexModel):
    """Represents a piece of legislation."""

    # Main information
    id: str
    uri: str
    title: str
    description: str
    # Dates
    enactment_date: Optional[date] = None
    valid_date: Optional[date] = None
    modified_date: Optional[date] = None
    # Metadata
    publisher: str
    category: LegislationCategory
    type: LegislationType
    year: int
    number: int
    status: str
    extent: List[GeographicalExtent] = Field(default_factory=list)
    number_of_provisions: int


class LegislationWithContent(Legislation):
    # Content
    sections: List[Section] = Field(default_factory=list)
    schedules: List[Schedule] = Field(default_factory=list)
    commentaries: Dict[str, Commentary] = Field(default_factory=list)

    def all_references(self) -> List[FreeTextReference]:
        """Return all references in the legislation including child elements."""
        references = []
        for section in self.sections:
            references.extend(section.all_references)
        for schedule in self.schedules:
            references.extend(schedule.all_references)
        return references

    def all_commentary_refs(self) -> List[str]:
        """Return all citations in the legislation including child elements."""
        commentary_refs = []
        for section in self.sections:
            commentary_refs.extend(section.all_commentary_refs)
        for schedule in self.schedules:
            commentary_refs.extend(schedule.all_commentary_refs)
        return commentary_refs

    def __str__(self) -> str:
        return (
            f"{self.title} ({self.id})\n"
            f"Description: {self.description}\n"
            f"Enactment Date: {self.enactment_date}\n"
            f"Valid Date: {self.valid_date}\n"
            f"Modified Date: {self.modified_date}\n"
            f"Publisher: {self.publisher}\n"
            f"Category: {self.category}\n"
            f"Type: {self.type}\n"
            f"Status: {self.status}\n"
            f"Extent: {self.extent}\n"
            f"Number of Provisions: {self.number_of_provisions}\n"
            f"Sections: {len(self.sections)}\n"
            f"Schedules: {len(self.schedules)}\n"
            f"References: {len(self.all_references())}"
        )


class LegislationSection(LexModel):
    id: str = Field(description="The ID of the section.")
    uri: str
    legislation_id: str = Field(description="The ID of the legislation.")
    title: str = Field(default_factory=str, description="The title of the section.")
    text: str = Field(description="The text of the section.")
    extent: List[GeographicalExtent] = Field(default_factory=list)
    provision_type: ProvisionType = ProvisionType.SECTION

    @computed_field
    @property
    def number(self) -> int | None:
        try:
            return int(self.id.split("/")[-1])
        except (IndexError, ValueError):
            return None

    @computed_field
    @property
    def legislation_type(self) -> LegislationType:
        """Return the type of the legislation."""
        try:
            return LegislationType(self.legislation_id.split("/")[4])
        except (IndexError, ValueError):
            return None

    @computed_field
    @property
    def legislation_year(self) -> int:
        """Return the year of the legislation."""
        try:
            return int(self.legislation_id.split("/")[5])
        except (IndexError, ValueError):
            return None

    @computed_field
    @property
    def legislation_number(self) -> int:
        """Return the number of the legislation."""
        try:
            return int(self.legislation_id.split("/")[6])
        except (IndexError, ValueError):
            return None

    @field_validator("text", mode="before")
    @classmethod
    def coerce_text_from_dict(cls, value):
        """If the input value is a dict with a 'text' key, extract it. This is to enable compatibility with the Elasticsearch output."""
        if isinstance(value, dict) and "text" in value:
            return value["text"]
        return value
