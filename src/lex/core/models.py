from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LexModel(BaseModel):
    """Base class for all Lex models that are exposed to the Elasticsearch indexes."""

    created_at: datetime = Field(default_factory=datetime.now)


class EmbeddableModel(LexModel):
    text: str

    @field_validator("text", mode="before")
    @classmethod
    def coerce_text_from_dict(cls, value):
        """If the input value is a dict with a 'text' key, extract it. This is to enable compatibility with the Elasticsearch output."""
        if isinstance(value, dict) and "text" in value:
            return value["text"]
        return value
