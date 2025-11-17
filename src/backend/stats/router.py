import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter
from qdrant_client.models import CountRequest

from lex.core.qdrant_client import qdrant_client
from lex.settings import (
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    EXPLANATORY_NOTE_SECTION_COLLECTION,
    AMENDMENT_COLLECTION,
)

router = APIRouter(tags=["stats"])
logger = logging.getLogger(__name__)


@router.get("/api/stats")
async def get_live_stats() -> Dict[str, Any]:
    """Get live dataset statistics for dynamic display."""
    # Get document counts from each collection
    legislation_count = qdrant_client.count(
        collection_name=LEGISLATION_COLLECTION,
        count_request=CountRequest(exact=True)
    ).count
    
    sections_count = qdrant_client.count(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        count_request=CountRequest(exact=True)
    ).count
    
    caselaw_count = qdrant_client.count(
        collection_name=CASELAW_COLLECTION,
        count_request=CountRequest(exact=True)
    ).count
    
    caselaw_sections_count = qdrant_client.count(
        collection_name=CASELAW_SECTION_COLLECTION,
        count_request=CountRequest(exact=True)
    ).count
    
    explanatory_count = qdrant_client.count(
        collection_name=EXPLANATORY_NOTE_SECTION_COLLECTION,
        count_request=CountRequest(exact=True)
    ).count
    
    amendments_count = qdrant_client.count(
        collection_name=AMENDMENT_COLLECTION,
        count_request=CountRequest(exact=True)
    ).count
    
    # Format numbers for display
    return {
        "acts_and_sis": f"{legislation_count:,}",
        "provisions": f"{sections_count:,}",
        "court_judgments": f"{caselaw_count:,}",
        "case_paragraphs": f"{caselaw_sections_count:,}",
        "explanatory_sections": f"{explanatory_count:,}",
        "amendments": f"{amendments_count:,}",
        "last_updated": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }