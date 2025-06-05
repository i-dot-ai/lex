from pydantic import BaseModel, Field


class Amendment(BaseModel):
    """
    A model for an amendment to a piece of legislation, taken from the legislation.gov.uk page.
    """

    changed_legislation: str
    changed_year: int
    changed_number: str
    changed_url: str
    changed_provision: str | None = Field(default=None)
    changed_provision_url: str | None = Field(default=None)
    affecting_legislation: str | None = Field(default=None)
    affecting_year: int | None = Field(default=None)
    affecting_number: str | None = Field(default=None)
    affecting_url: str
    affecting_provision: str | None = Field(default=None)
    affecting_provision_url: str | None = Field(default=None)
    type_of_effect: str | None = Field(default=None)
    id: str
