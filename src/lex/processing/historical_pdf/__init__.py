"""PDF digitization module for historical UK legislation."""

from lex.processing.historical_pdf.blob_uploader import LegislationBlobUploader
from lex.processing.historical_pdf.downloader import LegislationPDFDownloader, download_from_csv
from lex.processing.historical_pdf.metadata import fetch_pdf_metadata, fetch_xml_metadata
from lex.processing.historical_pdf.models import (
    ExtractionProvenance,
    ExtractionResult,
    LegislationMetadata,
    PDFMetadata,
)
from lex.processing.historical_pdf.processor import LegislationPDFProcessor

__all__ = [
    "LegislationPDFProcessor",
    "LegislationBlobUploader",
    "LegislationPDFDownloader",
    "download_from_csv",
    "fetch_xml_metadata",
    "fetch_pdf_metadata",
    "ExtractionResult",
    "ExtractionProvenance",
    "LegislationMetadata",
    "PDFMetadata",
]
