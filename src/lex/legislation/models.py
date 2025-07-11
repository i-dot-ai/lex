from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import Field, computed_field, field_validator

from lex.core.models import LexModel


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
