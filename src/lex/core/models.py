from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LexModel(BaseModel):
    """Base class for all Lex models."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, value: Any) -> datetime:
        """Ensure datetime is timezone-aware (handles legacy naive datetimes from Qdrant)."""
        if isinstance(value, str):
            # Handle both naive ISO strings and RFC 3339 with timezone
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
        return value


class EmbeddableModel(LexModel):
    text: str

    @field_validator("text", mode="before")
    @classmethod
    def coerce_text_from_dict(cls, value: Any) -> str:
        """Extract text from dict if present (handles nested text fields)."""
        if isinstance(value, dict) and "text" in value:
            return value["text"]
        return value

    def get_embedding_text(self) -> str:
        """Return text for embedding generation. Override in subclasses for richer context."""
        return self.text
