from datetime import datetime

from pydantic import BaseModel, Field

from lex.legislation.models import LegislationType


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

    # AI-generated explanation fields
    ai_explanation: str | None = Field(
        default=None,
        description="AI-generated plain English explanation of what this amendment does",
    )
    ai_explanation_model: str | None = Field(
        default=None, description="Model used to generate explanation (e.g., 'gpt-5-mini')"
    )
    ai_explanation_timestamp: datetime | None = Field(
        default=None, description="When the explanation was generated"
    )

    def get_embedding_text(self) -> str:
        """Generate rich contextual text for semantic embedding.

        Returns natural language description like:
        'Section 5 of UK Public General Act 2002 No. 1 was amended by
         Article 2 of UK Statutory Instrument 2017 No. 1283.
         Type of amendment: words substituted.
         Explanation: [AI explanation]'
        """
        parts = []

        # Changed provision reference
        changed_leg_type = self.changed_legislation.split("/")[0]
        try:
            changed_leg_name = LegislationType(changed_leg_type).get_display_name()
        except ValueError:
            changed_leg_name = changed_leg_type.upper()

        if self.changed_provision:
            # Clean up provision: "section/5" → "Section 5"
            prov = self.changed_provision.replace("/", " ").title()
            parts.append(f"{prov} of {changed_leg_name} {self.changed_year} No. {self.changed_number}")
        else:
            parts.append(f"{changed_leg_name} {self.changed_year} No. {self.changed_number}")

        # Affecting provision reference
        if self.affecting_legislation:
            affecting_leg_type = self.affecting_legislation.split("/")[0]
            try:
                affecting_leg_name = LegislationType(affecting_leg_type).get_display_name()
            except ValueError:
                affecting_leg_name = affecting_leg_type.upper()

            if self.affecting_provision:
                prov = self.affecting_provision.replace("/", " ").title()
                parts.append(f"was amended by {prov} of {affecting_leg_name} {self.affecting_year} No. {self.affecting_number}")
            else:
                parts.append(f"was amended by {affecting_leg_name} {self.affecting_year} No. {self.affecting_number}")

        # Type of effect
        if self.type_of_effect:
            parts.append(f"Type of amendment: {self.type_of_effect}.")

        # AI explanation (most important for semantic search)
        if self.ai_explanation:
            parts.append(f"Explanation: {self.ai_explanation}")

        return " ".join(parts)
