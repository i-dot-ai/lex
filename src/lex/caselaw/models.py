from datetime import date
from enum import Enum

from pydantic import Field

from lex.core.models import EmbeddableModel


class Court(str, Enum):
    """Courts in the UK legal system.

    This enum represents the various courts in the UK legal system:
    - UKSC: United Kingdom Supreme Court
    - UKPC: Privy Council
    - EWCA: Court of Appeal
    - EWHC: High Court (England and Wales)
    - EWCR: Crown Court
    - EWCC: County Court
    - EWFC: Family Court
    - EWCOP: Court of Protection
    - UKIPTRIB: Investigatory Powers Tribunal
    - EAT: Employment Appeal Tribunal
    - UKUT: Upper Tribunal
    - UKFTT: First-tier Tribunal
    """

    UKSC = "uksc"
    UKPC = "ukpc"
    EWCA = "ewca"
    EWHC = "ewhc"
    EWCR = "ewcr"
    EWCC = "ewcc"
    EWFC = "ewfc"
    EWCOP = "ewcop"
    UKIPTRIB = "ukiptrib"
    EAT = "eat"
    UKUT = "ukut"
    UKFTT = "ukftt"


class CourtDivision(str, Enum):
    """Divisions within UK courts.

    This enum represents the various divisions within courts:

    Court of Appeal (EWCA) divisions:
    - CIV: Civil Division
    - CRIM: Criminal Division

    High Court (EWHC) divisions:
    - ADMIN: Administrative Court
    - ADMLTY: Admiralty Court
    - CH: Chancery Division
    - COMM: Commercial Court
    - FAM: Family Division
    - IPEC: Intellectual Property Enterprise Court
    - KB: King's / Queen's Bench Division
    - MERCANTILE: Mercantile Court
    - PAT: Patents Court
    - SCCO: Senior Courts Costs Office
    - TCC: Technology and Construction Court
    - QB: Queen's Bench Division

    Upper Tribunal (UKUT) divisions:
    - AAC: Administrative Appeals Chamber
    - IAC: Immigration and Asylum Chamber
    - LC: Lands Chamber
    - TCC: Tax and Chancery Chamber

    First-tier Tribunal (UKFT) divisions:
    - GRC: General Regulatory Chamber
    - TC: Tax Chamber

    Family Court (EWFC) divisions:
    - B: Family Division
    """

    # Court of Appeal divisions
    CIV = "civ"
    CRIM = "crim"
    T3 = "t3"

    # High Court divisions
    ADMIN = "admin"
    ADMLTY = "admlty"
    CH = "ch"
    COMM = "comm"
    FAM = "fam"
    IPEC = "ipec"
    KB = "kb"
    MERCANTILE = "mercantile"
    PAT = "pat"
    SCCO = "scco"
    TCC = "tcc"
    QB = "qb"
    COSTS = "costs"

    # Upper Tribunal divisions
    AAC = "aac"
    IAC = "iac"
    LC = "lc"

    # First-tier Tribunal divisions
    GRC = "grc"
    TC = "tc"

    # Family Court divions
    B = "b"

    # Tier 2 divisions
    T2 = "t2"




class Caselaw(EmbeddableModel):
    id: str
    court: Court
    division: CourtDivision | None = Field(default=None)
    year: int
    number: int
    name: str
    cite_as: str | None = Field(default=None)
    date: date
    date_of: str
    header: str = Field(default_factory=str)
    text: str = Field(default_factory=str)
    caselaw_references: list[str] = Field(default_factory=list)
    legislation_references: list[str] = Field(default_factory=list)

    @property
    def content(self) -> str:
        text = f"Case {self.cite_as}"
        text += f"\nCourt {self.court.value} Division {self.division.value} Year {self.year} Number {self.number}"
        return text


class CaselawSection(EmbeddableModel):
    id: str
    caselaw_id: str
    court: Court
    division: CourtDivision | None = Field(default=None)
    year: int
    number: int
    cite_as: str
    route: list[str]
    order: int
