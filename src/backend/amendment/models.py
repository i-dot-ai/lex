from pydantic import BaseModel, Field


class AmendmentSearch(BaseModel):
    """Search for amendments at the legislation level."""

    legislation_id: str = Field(
        description="""ID of the legislation to search for (either amendments made to or amendments made by this legislation).""",
    )
    search_amended: bool = Field(
        default=True,
        description="If True, search for amendments made to the legislation. If False, search for amendments made by the legislation.",
    )
    size: int = Field(default=100, description="Maximum number of results to return.")


class AmendmentSectionSearch(BaseModel):
    """Search for amendments at the provision/section level."""

    provision_id: str = Field(
        description="ID of the provision/section to search for (either amendments made to or amendments made by this provision).",
    )
    search_amended: bool = Field(
        default=True,
        description="If True, search for amendments made to the provision. If False, search for amendments made by the provision.",
    )
    size: int = Field(default=100, description="Maximum number of results to return.")
