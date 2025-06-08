import logging
from typing import Iterator

from lex.core.document import generate_documents
from lex.core.exceptions import LexParsingError
from lex.legislation.loader import LegislationLoader
from lex.legislation.models import Legislation, LegislationSection, LegislationType
from lex.legislation.parser import LegislationParser, LegislationSectionParser
from lex.legislation.scraper import LegislationScraper

logger = logging.getLogger(__name__)


def pipe_legislation(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[Legislation]:
    scraper = LegislationScraper()
    parser = LegislationParser()
    loader = LegislationLoader()

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logging.info("Loading legislation from file")
    else:
        loader_or_scraper = scraper
        logging.info("Parsing legislation from web")

    # Pass checkpoint parameters if loading from web
    if loader_or_scraper == scraper:
        content_iterator = loader_or_scraper.load_content(
            years, limit, types,
            use_checkpoint=not kwargs.get("no_checkpoint", False),
            clear_checkpoint=kwargs.get("clear_checkpoint", False)
        )
    else:
        content_iterator = loader_or_scraper.load_content(years, limit, types)
    
    for soup in content_iterator:
        # Extract document identifier for logging
        doc_id = None
        try:
            # Try to find document identifier in the XML
            id_elem = soup.find("dc:identifier")
            if id_elem:
                doc_id = id_elem.text
            else:
                # Fallback to IdURI attribute
                legislation_elem = soup.find("Legislation")
                if legislation_elem and "IdURI" in legislation_elem.attrs:
                    doc_id = legislation_elem["IdURI"]
            
            if doc_id:
                logger.debug(f"Parsing document: {doc_id}")
            
            legislation = parser.parse_content(soup)
            yield from generate_documents([legislation], Legislation)
        except LexParsingError as e:
            # Extract metadata from error message if possible
            error_msg = str(e)
            doc_year = None
            doc_type = None
            
            # Try to extract ID from error message
            import re
            id_match = re.search(r'(http://www\.legislation\.gov\.uk/id/[^/]+/\d{4}/\d+)', error_msg)
            if id_match:
                doc_id = id_match.group(1)
                # Extract year and type from ID
                parts = doc_id.split('/')
                if len(parts) >= 6:
                    doc_type = parts[4]
                    doc_year = int(parts[5])
            
            # Determine if it's a PDF fallback
            is_pdf_fallback = "likely a pdf" in error_msg.lower() or "no body found" in error_msg.lower()
            
            logger.error(
                error_msg,
                extra={
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "doc_year": doc_year,
                    "processing_status": "pdf_fallback" if is_pdf_fallback else "parse_error",
                    "has_xml": False,
                    "error_type": "LexParsingError",
                    "is_pdf_fallback": is_pdf_fallback
                }
            )
        except Exception as e:
            logger.error(
                f"Error parsing legislation: {e}",
                exc_info=True,
                extra={
                    "doc_id": doc_id,
                    "processing_status": "error",
                    "error_type": type(e).__name__
                }
            )


def pipe_legislation_sections(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[LegislationSection]:
    scraper = LegislationScraper()
    parser = LegislationSectionParser()
    loader = LegislationLoader()

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logging.info("Loading legislation sections from file")
    else:
        loader_or_scraper = scraper
        logging.info("Parsing legislation sections from web")

    # Pass checkpoint parameters if loading from web
    if loader_or_scraper == scraper:
        content_iterator = loader_or_scraper.load_content(
            years, limit, types,
            use_checkpoint=not kwargs.get("no_checkpoint", False),
            clear_checkpoint=kwargs.get("clear_checkpoint", False)
        )
    else:
        content_iterator = loader_or_scraper.load_content(years, limit, types)
    
    for soup in content_iterator:
        # Extract document identifier for logging
        doc_id = None
        try:
            # Try to find document identifier in the XML
            id_elem = soup.find("dc:identifier")
            if id_elem:
                doc_id = id_elem.text
            else:
                # Fallback to IdURI attribute
                legislation_elem = soup.find("Legislation")
                if legislation_elem and "IdURI" in legislation_elem.attrs:
                    doc_id = legislation_elem["IdURI"]
            
            if doc_id:
                logger.debug(f"Parsing document sections: {doc_id}")
                
            legislation_sections = parser.parse_content(soup)
            
            # Log successful section extraction
            if legislation_sections:
                logger.info(
                    f"Successfully extracted {len(legislation_sections)} provisions from {doc_id}",
                    extra={
                        "doc_id": doc_id,
                        "provision_count": len(legislation_sections),
                        "processing_status": "provisions_extracted"
                    }
                )
            
            yield from generate_documents(legislation_sections, LegislationSection)
        except LexParsingError as e:
            # Extract metadata from error message if possible
            error_msg = str(e)
            doc_year = None
            doc_type = None
            
            # Try to extract ID from error message
            import re
            id_match = re.search(r'(http://www\.legislation\.gov\.uk/id/[^/]+/\d{4}/\d+)', error_msg)
            if id_match:
                doc_id = id_match.group(1)
                # Extract year and type from ID
                parts = doc_id.split('/')
                if len(parts) >= 6:
                    doc_type = parts[4]
                    doc_year = int(parts[5])
            
            # Determine if it's a PDF fallback
            is_pdf_fallback = "likely a pdf" in error_msg.lower() or "no body found" in error_msg.lower()
            
            logger.error(
                error_msg,
                extra={
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "doc_year": doc_year,
                    "processing_status": "pdf_fallback" if is_pdf_fallback else "parse_error",
                    "has_xml": False,
                    "error_type": "LexParsingError",
                    "is_pdf_fallback": is_pdf_fallback
                }
            )
        except Exception as e:
            logger.error(
                f"Error parsing legislation sections: {e}",
                exc_info=True,
                extra={
                    "doc_id": doc_id,
                    "processing_status": "error",
                    "error_type": type(e).__name__
                }
            )
