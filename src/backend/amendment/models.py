from pydantic import BaseModel, Field


class AmendmentSearch(BaseModel):
    """Search for amendments at the legislation level."""

    legislation_id: str = Field(
        description=(
            "ID of the legislation to search amendments for. "
            "Accepts short form (e.g., 'ukpga/1998/42') or full URL."
        ),
        examples=["ukpga/1998/42", "uksi/2018/12"],
    )
    search_amended: bool = Field(
        default=True,
        description="If True, search for amendments made to the legislation. If False, search for amendments made by the legislation.",
    )
    size: int = Field(default=100, description="Maximum number of results to return.")


class AmendmentSectionSearch(BaseModel):
    """Search for amendments at the provision/section level."""

    provision_id: str = Field(
        description=(
            "ID of the provision/section to search amendments for. "
            "Accepts short form (e.g., 'ukpga/1998/42/section/3') or full URL."
        ),
        examples=["ukpga/1998/42/section/3", "uksi/2018/12/regulation/5"],
    )
    search_amended: bool = Field(
        default=True,
        description="If True, search for amendments made to the provision. If False, search for amendments made by the provision.",
    )
    size: int = Field(default=100, description="Maximum number of results to return.")
