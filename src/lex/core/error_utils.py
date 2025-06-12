"""Error categorization and metadata extraction utilities."""

import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


class ErrorCategories:
    """Standard error categories across the pipeline."""
    PDF_FALLBACK = "pdf_fallback"
    HTTP_ERROR = "http_error"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    MEMORY_ERROR = "memory_error"
    ENCODING_ERROR = "encoding_error"
    FILE_ERROR = "file_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorCategorizer:
    """Categorize and extract metadata from errors in a consistent way."""

    # Error patterns for categorization
    ERROR_PATTERNS = {
        ErrorCategories.PDF_FALLBACK: [
            "no body found",
            "likely a pdf",
            "pdf fallback",
            "no xml content"
        ],
        ErrorCategories.HTTP_ERROR: [
            "httperror",
            "connectionerror",
            "timeout",
            "requestexception",
            "404",
            "403",
            "500",
            "502",
            "503",
            "504"
        ],
        ErrorCategories.PARSE_ERROR: [
            "lexparsingerror",
            "error parsing",
            "parseerror",
            "xml parse error",
            "invalid xml",
            "malformed",
            "syntax error"
        ],
        ErrorCategories.VALIDATION_ERROR: [
            "validation error",
            "validationerror",
            "invalid value",
            "missing required field",
            "commentarycitation"
        ],
        ErrorCategories.MEMORY_ERROR: [
            "memoryerror",
            "out of memory",
            "memory limit"
        ],
        ErrorCategories.ENCODING_ERROR: [
            "unicodedecodeerror",
            "unicodeencodeerror",
            "encoding error",
            "codec"
        ],
        ErrorCategories.FILE_ERROR: [
            "filenotfounderror",
            "ioerror",
            "permissionerror",
            "file not found",
            "access denied"
        ]
    }

    @classmethod
    def categorize_error(cls, error: Exception) -> str:
        """Categorize an error based on its type and message.
        
        Args:
            error: The exception to categorize
            
        Returns:
            Error category string
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # Check against patterns
        for category, patterns in cls.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern in error_str or pattern in error_type:
                    return category

        return ErrorCategories.UNKNOWN_ERROR

    @classmethod
    def extract_error_metadata(cls, error: Exception,
                             context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract structured metadata from an error.
        
        Args:
            error: The exception to analyze
            context: Optional context information
            
        Returns:
            Dictionary of error metadata
        """
        metadata = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_category": cls.categorize_error(error),
            "timestamp": datetime.now().isoformat()
        }

        # Extract document information from error message
        error_msg = str(error)

        # Extract URL
        url_match = re.search(r'https?://[^\s]+', error_msg)
        if url_match:
            metadata["error_url"] = url_match.group(0).rstrip(".,;)")

        # Extract document ID (flexible pattern)
        doc_patterns = [
            # Standard format: /type/year/number
            (r'/([a-z]+)/(\d{4})/(\d+)', 'standard'),
            # ID format: id/type/year/number
            (r'id/([a-z]+)/(\d{4})/(\d+)', 'id_format'),
            # Legislation.gov.uk format
            (r'legislation\.gov\.uk/([a-z]+)/(\d{4})/(\d+)', 'url_format')
        ]

        for pattern, format_type in doc_patterns:
            match = re.search(pattern, error_msg, re.IGNORECASE)
            if match:
                metadata["doc_id"] = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                metadata["doc_type"] = match.group(1)
                metadata["doc_year"] = int(match.group(2))
                metadata["doc_number"] = int(match.group(3))
                metadata["id_format"] = format_type
                break

        # Extract HTTP status code if present
        status_match = re.search(r'\b(40[0-9]|50[0-9])\b', error_msg)
        if status_match:
            metadata["http_status"] = int(status_match.group(0))

        # Add context if provided
        if context:
            metadata["context"] = context

        return metadata

    @classmethod
    def is_recoverable_error(cls, error: Exception) -> bool:
        """Determine if an error is recoverable (processing should continue).
        
        Args:
            error: The exception to check
            
        Returns:
            True if processing should continue, False if it should stop
        """
        category = cls.categorize_error(error)

        # These errors are expected and processing should continue
        recoverable_categories = {
            ErrorCategories.PDF_FALLBACK,  # Expected for old documents
            ErrorCategories.HTTP_ERROR,     # Individual document failures
            ErrorCategories.PARSE_ERROR,    # Individual document issues
            ErrorCategories.VALIDATION_ERROR,  # Data quality issues
            ErrorCategories.FILE_ERROR      # Missing files
        }

        return category in recoverable_categories

    @classmethod
    def get_error_summary(cls, error: Exception) -> str:
        """Get a concise summary of an error for logging.
        
        Args:
            error: The exception to summarize
            
        Returns:
            Concise error summary
        """
        category = cls.categorize_error(error)
        metadata = cls.extract_error_metadata(error)

        if category == ErrorCategories.PDF_FALLBACK:
            doc_id = metadata.get("doc_id", "unknown")
            return f"PDF fallback for {doc_id}"
        elif category == ErrorCategories.HTTP_ERROR:
            status = metadata.get("http_status", "unknown")
            url = metadata.get("error_url", "unknown")
            return f"HTTP {status} error for {url}"
        elif category == ErrorCategories.PARSE_ERROR:
            doc_id = metadata.get("doc_id", "unknown")
            return f"Parse error for {doc_id}"
        elif category == ErrorCategories.VALIDATION_ERROR:
            doc_id = metadata.get("doc_id", "unknown")
            return f"Validation error for {doc_id}"
        else:
            return f"{category}: {str(error)[:100]}..."

    @classmethod
    def handle_error(cls, logger, error: Exception, url: Optional[str] = None, context: Optional[Dict[str, Any]] = None, safe: bool = True) -> bool:
        """Handle an error by logging if recoverable or re-raising if not.
        
        Args:
            logger: Logger instance to use for error logging
            error: The exception to handle
            context: Optional context information for error metadata
            
        Returns:
            True if error was handled (recoverable), False if re-raised (non-recoverable)
            
        Raises:
            Exception: Re-raises the original error if it's non-recoverable
        """
        if cls.is_recoverable_error(error):
            logger.error(
                f"Failed to process {url}: {error}",
                extra=cls.extract_error_metadata(error, context)
            )
            return True
        else:
            # Non-recoverable error - re-raise
            logger.error(
                f"Failed to process - non recoverable:{url}: {error}",
                extra=cls.extract_error_metadata(error, context)
            )
            if not safe:
                raise error


def categorize_batch_errors(errors: list[Tuple[str, Exception]]) -> Dict[str, list]:
    """Categorize a batch of errors for reporting.
    
    Args:
        errors: List of (url, exception) tuples
        
    Returns:
        Dictionary mapping categories to error details
    """
    categorized = {}

    for url, error in errors:
        category = ErrorCategorizer.categorize_error(error)
        metadata = ErrorCategorizer.extract_error_metadata(error)
        metadata["url"] = url

        if category not in categorized:
            categorized[category] = []
        categorized[category].append(metadata)

    return categorized
