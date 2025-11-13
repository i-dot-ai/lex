"""URL-level tracking with run IDs and document dates for full audit trail."""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Configurable via environment variable, defaults to data/tracking in project root
TRACKER_DIR = Path(os.getenv("LEX_TRACKER_DIR", "data/tracking"))


@dataclass
class SuccessRecord:
    url: str
    uuid: str
    run_id: str
    doc_type: str
    year: int
    type_value: Optional[str]
    doc_date: Optional[str]
    timestamp: str


@dataclass
class FailureRecord:
    url: str
    error: str
    run_id: str
    doc_type: str
    year: int
    type_value: Optional[str]
    timestamp: str


class URLTracker:
    """Track successful and failed URLs with append-only JSONL logs."""

    def __init__(
        self,
        doc_type: str,
        year: int,
        type_value: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        self.doc_type = doc_type
        self.year = year
        self.type_value = type_value
        self.run_id = run_id or str(uuid.uuid4())

        # Separate files per year/type
        identifier = f"{doc_type}_{year}_{type_value}" if type_value else f"{doc_type}_{year}"
        self.success_file = TRACKER_DIR / f"{identifier}_success.jsonl"
        self.failure_file = TRACKER_DIR / f"{identifier}_failures.jsonl"

        TRACKER_DIR.mkdir(parents=True, exist_ok=True)

        # Cache processed URLs in memory for fast lookup
        self._processed_urls = self._load_processed_urls()

        logger.info(
            f"URLTracker initialized: run_id={self.run_id}, {len(self._processed_urls)} URLs already processed"
        )

    def is_processed(self, url: str) -> bool:
        """Check if URL has already been successfully processed."""
        return url in self._processed_urls

    def record_success(self, url: str, doc_uuid: str, doc_date: Optional[str] = None):
        """Record successful processing.

        Args:
            url: The URL that was processed
            doc_uuid: The Qdrant UUID for this document
            doc_date: The document's own date (e.g., publication date, enactment date)
        """
        record = SuccessRecord(
            url=url,
            uuid=doc_uuid,
            run_id=self.run_id,
            doc_type=self.doc_type,
            year=self.year,
            type_value=self.type_value,
            doc_date=doc_date,
            timestamp=datetime.utcnow().isoformat(),
        )

        with open(self.success_file, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

        self._processed_urls.add(url)
        logger.debug(f"Recorded success: {url} -> {doc_uuid}")

    def record_failure(self, url: str, error: str):
        """Record processing failure."""
        record = FailureRecord(
            url=url,
            error=error,
            run_id=self.run_id,
            doc_type=self.doc_type,
            year=self.year,
            type_value=self.type_value,
            timestamp=datetime.utcnow().isoformat(),
        )

        with open(self.failure_file, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

        logger.debug(f"Recorded failure: {url} - {error[:100]}")

    def _load_processed_urls(self) -> set:
        """Load all successfully processed URLs into memory."""
        processed = set()

        if self.success_file.exists():
            with open(self.success_file) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        processed.add(record["url"])

        return processed

    def get_stats(self) -> dict:
        """Get success/failure counts."""
        success_count = len(self._processed_urls)

        failure_count = 0
        if self.failure_file.exists():
            with open(self.failure_file) as f:
                failure_count = sum(1 for line in f if line.strip())

        return {
            "success": success_count,
            "failures": failure_count,
            "total": success_count + failure_count,
        }


def clear_tracking(doc_type: str):
    """Clear all tracking files for a document type."""
    import glob

    pattern = str(TRACKER_DIR / f"{doc_type}_*")
    for file in glob.glob(pattern):
        Path(file).unlink()
    logger.info(f"Cleared all tracking for {doc_type}")
