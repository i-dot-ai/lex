"""
Data models for PDF digitization with provenance tracking.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExtractionProvenance(BaseModel):
    """Provenance metadata for LLM-extracted content."""

    source: Literal["llm_ocr"] = "llm_ocr"
    model: str = Field(..., description="LLM model used (e.g., gpt-5-mini)")
    prompt_version: str = Field(..., description="Prompt version identifier (e.g., v1.0)")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When extraction occurred"
    )
    processing_time_seconds: float = Field(..., description="Time taken to process")
    input_tokens: int = Field(..., description="Number of input tokens")
    output_tokens: int = Field(..., description="Number of output tokens")
    cached_tokens: int = Field(default=0, description="Number of cached tokens")
    response_id: str = Field(..., description="Azure OpenAI response ID for tracing")


class ExtractionResult(BaseModel):
    """Result of PDF extraction with provenance."""

    extracted_data: str = Field(..., description="Extracted JSON content")
    provenance: ExtractionProvenance = Field(..., description="Extraction provenance metadata")
    success: bool = Field(default=True, description="Whether extraction succeeded")
    error: str | None = Field(default=None, description="Error message if failed")
    pdf_source: str = Field(default="", description="Source PDF URL or path")
    legislation_type: str | None = Field(default=None, description="Legislation type (e.g., ukpga)")
    identifier: str | None = Field(
        default=None, description="Legislation identifier (e.g., Edw7/6/19)"
    )


class PDFMetadata(BaseModel):
    """PDF file metadata."""

    file_size_bytes: int | None = None
    page_count: int | None = None
    pdf_url: str | None = None


class LegislationMetadata(BaseModel):
    """Minimal metadata from legislation.gov.uk XML and PDF."""

    title: str | None = None
    year: str | None = None
    number: str | None = None
    enactment_date: str | None = None
    type: str | None = None
    pdf: PDFMetadata | None = None

    def to_prompt_context(self) -> str:
        """Convert to prompt context string."""
        parts = []

        if self.title:
            parts.append(f"Title: {self.title}")
        if self.year:
            parts.append(f"Year: {self.year}")
        if self.number:
            parts.append(f"Chapter Number: {self.number}")
        if self.enactment_date:
            parts.append(f"Enactment Date: {self.enactment_date}")
        if self.pdf and self.pdf.page_count:
            parts.append(f"PDF Pages: {self.pdf.page_count}")

        return "\n".join(parts) if parts else ""
