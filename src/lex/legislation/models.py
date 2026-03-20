from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from lex.core.models import EmbeddableModel


class LegislationCategory(str, Enum):
    """High-level categorisation of legislation types.

    This enum represents the three main categories of legislation:
    - PRIMARY: Main acts of parliament and assemblies
    - SECONDARY: Statutory instruments and rules
    - EUROPEAN: EU-derived legislation (Decisions, Directives, Regulations)
    - EUROPEAN_RETAINED: EU-derived legislation retained in UK law
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

    def get_display_name(self) -> str:
        """Get the full human-readable name for this legislation type."""
        display_names = {
            LegislationType.UKPGA: "UK Public General Act",
            LegislationType.ASP: "Act of the Scottish Parliament",
            LegislationType.ASC: "Act of Senedd Cymru",
            LegislationType.ANAW: "Act of the National Assembly for Wales",
            LegislationType.WSI: "Wales Statutory Instrument",
            LegislationType.UKSI: "UK Statutory Instrument",
            LegislationType.SSI: "Scottish Statutory Instrument",
            LegislationType.UKCM: "Church Measure",
            LegislationType.NISR: "Northern Ireland Statutory Rule",
            LegislationType.NIA: "Northern Ireland Act",
            LegislationType.EUDN: "EU Decision",
            LegislationType.EUDR: "EU Directive",
            LegislationType.EUR: "EU Regulation",
            LegislationType.UKLA: "UK Local Act",
            LegislationType.UKPPA: "UK Private and Personal Act",
            LegislationType.APNI: "Act of the Northern Ireland Parliament",
            LegislationType.GBLA: "Local Act of the Parliament of Great Britain",
            LegislationType.AOSP: "Act of the Old Scottish Parliament",
            LegislationType.AEP: "Act of the English Parliament",
            LegislationType.APGB: "Act of the Parliament of Great Britain",
            LegislationType.MWA: "Measure of the Welsh Assembly",
            LegislationType.AIP: "Act of the Old Irish Parliament",
            LegislationType.MNIA: "Measure of the Northern Ireland Assembly",
            LegislationType.NISRO: "Northern Ireland Statutory Rule and Order",
            LegislationType.NISI: "Northern Ireland Order in Council",
            LegislationType.UKSRO: "UK Statutory Rule and Order",
            LegislationType.UKMO: "UK Ministerial Order",
            LegislationType.UKCI: "Church Instrument",
        }
        return display_names.get(self, self.value.upper())

    @staticmethod
    def filter_by_year(types: list["LegislationType"], year: int) -> list["LegislationType"]:
        """
        Filter legislation types by their historical active years.

        Based on legislation.gov.uk documentation:
        - AEP (1267-1707) - Acts of English Parliament
        - AOSP (1424-1707) - Acts of Old Scottish Parliament
        - AIP (1495-1800) - Acts of Old Irish Parliament
        - UKPPA (1539-present) - UK Private and Personal Acts
        - APGB (1707-1800) - Acts of Parliament of Great Britain
        - UKLA (1797-present) - UK Local Acts
        - GBLA (1797-1800) - Local Acts of Parliament of GB
        - UKPGA (1801-present) - UK Public General Acts
        - UKSRO (1894-1947) - UK Statutory Rules and Orders
        - UKCM (1920-present) - Church Measures
        - APNI (1921-1972) - Acts of NI Parliament
        - UKSI (1948-present) - UK Statutory Instruments
        - ASP (1999-present) - Acts of Scottish Parliament
        - Other modern types (1999+)

        Args:
            types: list of legislation types to filter
            year: Year to filter by

        Returns:
            list of legislation types valid for the given year
        """
        type_year_ranges = {
            LegislationType.AEP: (1267, 1707),
            LegislationType.AOSP: (1424, 1707),
            LegislationType.AIP: (1495, 1800),
            LegislationType.UKPPA: (1539, 9999),
            LegislationType.APGB: (1707, 1800),
            LegislationType.UKLA: (1797, 9999),
            LegislationType.GBLA: (1797, 1800),
            LegislationType.UKPGA: (1801, 9999),
            LegislationType.UKSRO: (1894, 1947),
            LegislationType.UKCM: (1920, 9999),
            LegislationType.APNI: (1921, 1972),
            LegislationType.UKSI: (1948, 9999),
            LegislationType.ASP: (1999, 9999),
            LegislationType.SSI: (1999, 9999),
            LegislationType.NIA: (2000, 9999),
            LegislationType.NISR: (2000, 9999),
            LegislationType.MWA: (2008, 2011),
            LegislationType.ANAW: (2012, 2020),
            LegislationType.WSI: (2012, 9999),
            LegislationType.ASC: (2020, 9999),
            # EU types (1973-2020)
            LegislationType.EUR: (1973, 2020),
            LegislationType.EUDR: (1973, 2020),
            LegislationType.EUDN: (1973, 2020),
            # Other secondary types
            LegislationType.NISRO: (1922, 1974),
            LegislationType.NISI: (1974, 9999),
            LegislationType.UKCI: (1991, 9999),
            LegislationType.MNIA: (1974, 1974),
            # UKMO - various years, keep always
            LegislationType.UKMO: (1800, 9999),
        }

        filtered = []
        for leg_type in types:
            year_range = type_year_ranges.get(leg_type)
            if year_range:
                start_year, end_year = year_range
                if start_year <= year <= end_year:
                    filtered.append(leg_type)

        return filtered


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
    context: str | None = None


class CommentaryCitation(BaseModel):
    """A reference to a commentary citation."""

    id: str
    uri: str
    type: str
    context: str | None = None
    section_ref: str | None = None
    citation_ref: str | None = None
    citation_type: str | None = None  # primary or sub_reference


class FreeTextReference(BaseModel):
    """A reference to another legislative element by free text."""

    source_id: str
    context: str
    act: str | None = None
    section: str | None = None
    type: str | None = None

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
    references: list[FreeTextReference] = Field(default_factory=list)
    commentary_refs: list[str] = Field(default_factory=list)

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
    paragraph_id: str | None = None


class Provision(LegislativeText):
    """Represents the generic concept of a provision within legislation."""

    number: str
    title: str = Field(default_factory=str)
    extent: list[GeographicalExtent] = Field(default_factory=list)
    legislation_id: str
    paragraphs: list[Paragraph] = Field(default_factory=list)

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
    def all_references(self) -> list[FreeTextReference]:
        """Return all references in the section and its child paragraphs."""
        references = []
        for paragraph in self.paragraphs:
            references.extend(paragraph.references)
        return self.references + references

    @property
    def all_commentary_refs(self) -> list[str]:
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
    citations: list[CommentaryCitation] = Field(default_factory=list)
    text: str


class Legislation(EmbeddableModel):
    """Represents a piece of legislation."""

    # Main information
    id: str
    uri: str
    title: str
    description: str
    text: str = Field(default="", description="Combined text content of the legislation.")
    # Dates
    enactment_date: date | None = None
    valid_date: date | None = None
    modified_date: date | None = None
    # Metadata
    publisher: str
    category: LegislationCategory
    type: LegislationType
    year: int
    number: int
    status: str
    extent: list[GeographicalExtent] = Field(default_factory=list)
    number_of_provisions: int
    # Provenance tracking (for LLM-extracted PDF content)
    provenance_source: Literal["xml", "llm_ocr"] | None = None
    provenance_model: str | None = None
    provenance_prompt_version: str | None = None
    provenance_timestamp: datetime | None = None
    provenance_response_id: str | None = None

    def get_embedding_text(self) -> str:
        """Return text for embedding generation with title and description context."""
        return f"{self.title}\n\n{self.description}\n\n{self.text}"


class LegislationWithContent(Legislation):
    # Content
    sections: list[Section] = Field(default_factory=list)
    schedules: list[Schedule] = Field(default_factory=list)
    commentaries: dict[str, Commentary] = Field(default_factory=dict)

    def all_references(self) -> list[FreeTextReference]:
        """Return all references in the legislation including child elements."""
        references = []
        for section in self.sections:
            references.extend(section.all_references)
        for schedule in self.schedules:
            references.extend(schedule.all_references)
        return references

    def all_commentary_refs(self) -> list[str]:
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


# Regnal year monarch prefixes mapped to reign start/end years.
# Used to resolve pre-1963 legislation URIs that use regnal year numbering
# (e.g. http://www.legislation.gov.uk/id/ukla/Vict/44-45/12).
_REGNAL_YEAR_RANGES = {
    "Hen3": (1216, 1272),
    "Edw1": (1272, 1307),
    "Edw2": (1307, 1327),
    "Edw3": (1327, 1377),
    "Ric2": (1377, 1399),
    "Hen4": (1399, 1413),
    "Hen5": (1413, 1422),
    "Hen6": (1422, 1461),
    "Edw4": (1461, 1483),
    "Ric3": (1483, 1485),
    "Hen7": (1485, 1509),
    "Hen8": (1509, 1547),
    "Edw6": (1547, 1553),
    "Mar1": (1553, 1558),  # Mary I / Philip & Mary
    "Eliz1": (1558, 1603),
    "Jas1": (1603, 1625),  # James I
    "Cha1": (1625, 1649),  # Charles I
    "Cha2": (1660, 1685),  # Charles II
    "Will3": (1689, 1702),  # William III / William & Mary
    "WillandMar": (1689, 1694),
    "Ann": (1702, 1714),
    "Geo1": (1714, 1727),
    "Geo2": (1727, 1760),
    "Geo3": (1760, 1820),
    "Geo4": (1820, 1830),
    "Will4": (1830, 1837),
    "Vict": (1837, 1901),
    "Edw7": (1901, 1910),
    "Geo5": (1910, 1936),
    "Geo6": (1936, 1952),
    "Eliz2": (1952, 2022),
}


def _parse_year_from_legislation_id(legislation_id: str) -> int | None:
    """Parse calendar year from a legislation_id, handling regnal year URIs.

    Standard URI: http://www.legislation.gov.uk/id/ukpga/2018/12 → 2018
    Regnal URI:   http://www.legislation.gov.uk/id/ukla/Vict/44-45/12 → 1881 (1837 + 44)
    """
    if not legislation_id:
        return None
    parts = legislation_id.split("/")
    if len(parts) < 6:
        return None

    year_part = parts[5]

    # Standard numeric year
    try:
        return int(year_part)
    except ValueError:
        pass

    # Regnal year — match monarch prefix
    for prefix, (reign_start, _reign_end) in _REGNAL_YEAR_RANGES.items():
        if year_part == prefix or year_part.startswith(prefix):
            # Session number follows (e.g. "Geo5" at [5], "14-15" at [6])
            if len(parts) > 6:
                session_part = parts[6]
                try:
                    # Take the first session year (e.g. "14" from "14-15")
                    session = int(session_part.split("-")[0])
                    return reign_start + session
                except (ValueError, IndexError):
                    pass
            return reign_start

    return None


class LegislationSection(EmbeddableModel):
    id: str = Field(description="The ID of the section.")
    uri: str
    legislation_id: str = Field(description="The ID of the legislation.")
    title: str = Field(default_factory=str, description="The title of the section.")
    text: str = Field(default="", description="The text of the section.")
    extent: list[GeographicalExtent] = Field(default_factory=list)
    provision_type: ProvisionType = ProvisionType.SECTION
    # Provenance tracking (for LLM-extracted PDF content)
    provenance_source: Literal["xml", "llm_ocr"] | None = None
    provenance_model: str | None = None
    provenance_prompt_version: str | None = None
    provenance_timestamp: datetime | None = None
    provenance_response_id: str | None = None

    def get_embedding_text(self) -> str:
        """Return text for embedding generation with title context."""
        return f"{self.title}\n\n{self.text}"

    @computed_field
    @property
    def number(self) -> int | None:
        try:
            return int(self.id.split("/")[-1])
        except (IndexError, ValueError):
            return None

    @computed_field
    @property
    def legislation_type(self) -> LegislationType | None:
        """Return the type of the legislation."""
        try:
            return LegislationType(self.legislation_id.split("/")[4])
        except (IndexError, ValueError):
            return None

    @computed_field
    @property
    def legislation_year(self) -> int | None:
        """Return the year of the legislation, handling regnal year URIs."""
        return _parse_year_from_legislation_id(self.legislation_id)

    @computed_field
    @property
    def legislation_number(self) -> int | None:
        """Return the number of the legislation."""
        # For regnal year URIs the number is at a different index,
        # so take the last numeric path component
        try:
            parts = self.legislation_id.split("/")
            # Try standard position first (index 6)
            try:
                return int(parts[6])
            except (IndexError, ValueError):
                pass
            # Fall back to last component
            for part in reversed(parts):
                try:
                    return int(part)
                except ValueError:
                    continue
            return None
        except (IndexError, ValueError):
            return None

    @field_validator("text", mode="before")
    @classmethod
    def coerce_text_from_dict(cls, value):
        """Extract text from nested dict structures if present."""
        if isinstance(value, dict) and "text" in value:
            return value["text"]
        return value
