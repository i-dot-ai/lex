#!/usr/bin/env python
"""
Create payload indexes for all Qdrant collections.

This script applies payload indexes to existing collections to dramatically
improve filter query performance (from 60s to <100ms for exact match queries).

Run this after updating qdrant_schema.py files with payload_schema definitions.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from qdrant_client.models import PayloadSchemaType

from lex.amendment.qdrant_schema import get_amendment_schema
from lex.caselaw.qdrant_schema import get_caselaw_schema, get_caselaw_section_schema
from lex.explanatory_note.qdrant_schema import get_explanatory_note_schema
from lex.legislation.qdrant_schema import get_legislation_schema, get_legislation_section_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Qdrant client using the same method as the main application
from lex.core.qdrant_client import get_qdrant_client

qdrant_client = get_qdrant_client()


def create_index(collection_name: str, field_name: str, field_type: PayloadSchemaType):
    """Create a single payload index (async, returns immediately)."""
    try:
        result = qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=field_type,
            wait=False,  # Don't wait for completion - return immediately
        )
        logger.info(
            f"✓ Initiated index on {collection_name}.{field_name} (operation_id: {result.operation_id})"
        )
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"⊙ Index already exists on {collection_name}.{field_name}")
            return True
        logger.error(f"✗ Failed to create index on {collection_name}.{field_name}: {e}")
        return False


def apply_payload_indexes():
    """Apply all payload indexes from schema definitions."""

    # Get all schemas
    schemas = [
        get_legislation_schema(),
        get_legislation_section_schema(),
        get_caselaw_schema(),
        get_caselaw_section_schema(),
        get_explanatory_note_schema(),
        get_amendment_schema(),
    ]

    total_indexes = 0
    successful_indexes = 0

    for schema in schemas:
        collection_name = schema["collection_name"]
        payload_schema = schema.get("payload_schema", {})

        if not payload_schema:
            logger.info(f"⊘ No payload indexes defined for {collection_name}")
            continue

        logger.info(f"\n📋 Processing {collection_name} ({len(payload_schema)} indexes)")
        logger.info("=" * 80)

        for field_name, field_type in payload_schema.items():
            total_indexes += 1
            if create_index(collection_name, field_name, field_type):
                successful_indexes += 1

    logger.info("\n" + "=" * 80)
    logger.info(f"✓ Successfully created {successful_indexes}/{total_indexes} indexes")

    if successful_indexes < total_indexes:
        logger.warning(f"⚠ {total_indexes - successful_indexes} indexes failed (may already exist)")

    logger.info("\n📊 Monitoring index build progress...")
    logger.info(
        "Use: curl http://localhost:6333/collections/<collection_name> | jq '.result.payload_schema'"
    )


def main():
    """Main execution."""
    logger.info("Qdrant Payload Index Creator")
    logger.info("=" * 80)
    logger.info("")

    apply_payload_indexes()


if __name__ == "__main__":
    main()
