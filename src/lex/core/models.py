from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LexModel(BaseModel):
    """Base class for all Lex models."""

    created_at: datetime = Field(default_factory=datetime.now)


class EmbeddableModel(LexModel):
    text: str

    @field_validator("text", mode="before")
    @classmethod
    def coerce_text_from_dict(cls, value):
        """Extract text from dict if present (handles nested text fields)."""
        if isinstance(value, dict) and "text" in value:
            return value["text"]
        return value
