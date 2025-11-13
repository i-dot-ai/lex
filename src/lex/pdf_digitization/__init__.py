"""PDF digitization module for historical UK legislation."""

from lex.pdf_digitization.blob_uploader import LegislationBlobUploader
from lex.pdf_digitization.downloader import LegislationPDFDownloader, download_from_csv
from lex.pdf_digitization.metadata import fetch_pdf_metadata, fetch_xml_metadata
from lex.pdf_digitization.models import (
                                             ExtractionProvenance,
                                             ExtractionResult,
                                             LegislationMetadata,
                                             PDFMetadata,
)
from lex.pdf_digitization.processor import LegislationPDFProcessor

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
