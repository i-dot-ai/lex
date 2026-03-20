#!/usr/bin/env python
"""Enable scalar quantization on Qdrant collections for improved performance.

This script enables INT8 scalar quantization which:
- Reduces memory usage by 75% (4 bytes -> 1 byte per dimension)
- Speeds up search by 20-30% (fewer memory bus transfers)
- Maintains <1% accuracy loss (Qdrant rescores with original vectors)

The optimization process runs in the background and may take 10-30 minutes
depending on collection size.
"""

import logging
import os
import sys

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import ScalarQuantization, ScalarQuantizationConfig, ScalarType

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Use cloud Qdrant by default
QDRANT_URL = os.getenv("QDRANT_CLOUD_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_CLOUD_API_KEY")

COLLECTIONS = [
    "legislation",
    "legislation_section",
    "caselaw",
    "caselaw_section",
    "amendment",
    "explanatory_note",
]


def enable_quantization(client: QdrantClient, collection_name: str):
    """Enable scalar quantization on a collection."""
    try:
        logger.info(f"Enabling INT8 quantization for {collection_name}...")

        client.update_collection(
            collection_name=collection_name,
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,  # Exclude 1% outliers for better compression
                    always_ram=True,  # Keep quantized vectors in RAM for speed
                )
            ),
        )

        logger.info(f"✓ Quantization enabled for {collection_name}")
        logger.info("  Background optimization started - this may take 10-30 minutes")
        logger.info(f"  Check status: curl http://localhost:6333/collections/{collection_name}")

    except Exception as e:
        logger.error(f"✗ Failed to enable quantization for {collection_name}: {e}")
        raise


def check_collection_status(client: QdrantClient, collection_name: str):
    """Check optimization status of a collection."""
    try:
        info = client.get_collection(collection_name)
        status = info.status
        optimizer_status = info.optimizer_status

        logger.info(f"\n{collection_name} status:")
        logger.info(f"  Collection status: {status}")
        logger.info(f"  Optimizer status: {optimizer_status}")

        if status == "green":
            logger.info(f"  ✓ {collection_name} is fully optimized")
            return True
        else:
            logger.info(f"  ⏳ {collection_name} is still optimizing (status: {status})")
            return False

    except Exception as e:
        logger.error(f"Failed to check status for {collection_name}: {e}")
        return False


def main():
    """Enable quantization on all configured collections."""
    logger.info("Starting quantization migration...")
    logger.info(f"Qdrant URL: {QDRANT_URL}")
    logger.info(f"Collections: {', '.join(COLLECTIONS)}\n")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=360)

    # Enable quantization on all collections
    for collection in COLLECTIONS:
        try:
            enable_quantization(client, collection)
        except Exception as e:
            logger.error(f"Failed to process {collection}: {e}")
            sys.exit(1)

    # Check initial status
    logger.info("\n" + "=" * 60)
    logger.info("Quantization enabled on all collections")
    logger.info("=" * 60)

    for collection in COLLECTIONS:
        check_collection_status(client, collection)

    logger.info("\n" + "=" * 60)
    logger.info("Next steps:")
    logger.info("=" * 60)
    logger.info("1. Monitor optimization progress:")
    for collection in COLLECTIONS:
        logger.info(f"   curl http://localhost:6333/collections/{collection} | jq .result.status")
    logger.info("\n2. Wait until all collections show status='green'")
    logger.info("3. Run performance tests to validate improvements")
    logger.info("4. Expected results:")
    logger.info("   - 75% memory reduction")
    logger.info("   - 20-30% search speedup")
    logger.info("   - <1% accuracy loss")


if __name__ == "__main__":
    main()
