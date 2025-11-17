import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from functools import lru_cache

from fastapi import APIRouter
from qdrant_client.models import FieldCondition, Filter, MatchValue

from lex.core.qdrant_client import qdrant_client
from lex.settings import (
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    AMENDMENT_COLLECTION,
)

router = APIRouter(tags=["stats"])
logger = logging.getLogger(__name__)

# Cache stats for 5 minutes to reduce Qdrant load
@lru_cache(maxsize=1)
def _get_cached_stats(cache_key: str) -> Dict[str, Any]:
    """Get cached stats with 5-minute expiry."""
    return _calculate_live_stats()

def _calculate_live_stats() -> Dict[str, Any]:
    """Calculate live statistics from Qdrant collections."""


    # Get document counts from each collection
    legislation_count = qdrant_client.count(
        collection_name=LEGISLATION_COLLECTION,
        exact=True
    ).count
    
    sections_count = qdrant_client.count(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        exact=True
    ).count
    
    caselaw_count = qdrant_client.count(
        collection_name=CASELAW_COLLECTION,
        exact=True
    ).count
    
    caselaw_sections_count = qdrant_client.count(
        collection_name=CASELAW_SECTION_COLLECTION,
        exact=True
    ).count
    
    explanatory_count = qdrant_client.count(
        collection_name=EXPLANATORY_NOTE_COLLECTION,
        exact=True
    ).count
    
    amendments_count = qdrant_client.count(
        collection_name=AMENDMENT_COLLECTION,
        exact=True
    ).count
    
    # Count PDF-derived legislation (LLM OCR provenance)
    pdf_legislation_count = qdrant_client.count(
        collection_name=LEGISLATION_COLLECTION,
        exact=True,
        count_filter=Filter(
            must=[FieldCondition(
                key="provenance_source",
                match=MatchValue(value="llm_ocr")
            )]
        )
    ).count
    
    # Count PDF-derived sections
    pdf_sections_count = qdrant_client.count(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        exact=True,
        count_filter=Filter(
            must=[FieldCondition(
                key="provenance_source",
                match=MatchValue(value="llm_ocr")
            )]
        )
    ).count
    
    # Format numbers for display
    return {
        "acts_and_sis": f"{legislation_count:,}",
        "provisions": f"{sections_count:,}",
        "court_judgments": f"{caselaw_count:,}",
        "case_paragraphs": f"{caselaw_sections_count:,}",
        "explanatory_sections": f"{explanatory_count:,}",
        "amendments": f"{amendments_count:,}",
        "pdf_legislation": f"{pdf_legislation_count:,}",
        "pdf_provisions": f"{pdf_sections_count:,}",
        "last_updated": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }

@router.get("/api/stats")
async def get_live_stats() -> Dict[str, Any]:
    """Get live dataset statistics with 5-minute caching."""
    # Use current time rounded to 5-minute intervals as cache key
    now = datetime.now(timezone.utc)
    cache_key = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).isoformat()
    
    return _get_cached_stats(cache_key)