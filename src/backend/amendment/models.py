from pydantic import BaseModel, Field


class AmendmentSearch(BaseModel):
    legislation_id: str = Field(
        description="Full legislation ID (e.g. http://www.legislation.gov.uk/id/ukpga/2018/12) to find amendments for.",
    )
    search_amended: bool = Field(
        default=True,
        description="True: find amendments made TO this legislation. False: find amendments made BY this legislation to other laws.",
    )
    size: int = Field(default=100, description="Maximum number of results to return.")


class AmendmentSectionSearch(BaseModel):
    provision_id: str = Field(
        description="Full provision ID (e.g. http://www.legislation.gov.uk/id/ukpga/2018/12/section/5) to find amendments for.",
    )
    search_amended: bool = Field(
        default=True,
        description="True: find amendments made TO this provision. False: find amendments made BY this provision to other laws.",
    )
    size: int = Field(default=100, description="Maximum number of results to return.")
