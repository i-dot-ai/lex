"""
Create Azure Blob Storage container for historical legislation PDFs.

Usage:
    uv run python scripts/setup_azure_storage.py
"""

import logging
import os
from pathlib import Path

from azure.storage.blob import BlobServiceClient, PublicAccess
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_container():
    """Create Azure Blob Storage container with hierarchical namespace support."""

    # Get credentials from environment
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "historical-legislation-pdfs")

    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not found in environment")

    logger.info(f"Connecting to Azure Storage...")

    # Create BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    # Create private container (will use SAS tokens for Azure OpenAI access)
    try:
        container_client = blob_service_client.create_container(
            name=container_name
            # No public_access = private container
        )
        logger.info(f"✅ Container '{container_name}' created successfully")
        logger.info(f"   Access: Private (will use SAS tokens for Azure OpenAI)")

    except Exception as e:
        if "ContainerAlreadyExists" in str(e):
            logger.info(f"✅ Container '{container_name}' already exists")
            container_client = blob_service_client.get_container_client(container_name)
        else:
            raise

    # Get container URL
    container_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}"
    logger.info(f"   Container URL: {container_url}")

    # List existing blobs (if any)
    blob_list = container_client.list_blobs()
    blob_count = sum(1 for _ in blob_list)
    logger.info(f"   Existing blobs: {blob_count}")

    return container_client


def test_upload():
    """Test uploading a small file to verify connectivity."""

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "historical-legislation-pdfs")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    # Create a test file
    test_content = b"Test PDF placeholder for Azure Blob Storage verification"
    test_blob_name = "_test/test.txt"

    logger.info(f"Uploading test file: {test_blob_name}")

    blob_client = container_client.get_blob_client(test_blob_name)
    blob_client.upload_blob(test_content, overwrite=True)

    test_url = blob_client.url
    logger.info(f"✅ Test upload successful!")
    logger.info(f"   URL: {test_url}")
    logger.info(f"   Try accessing: {test_url}")

    return test_url


if __name__ == "__main__":
    print("=" * 80)
    print("Azure Blob Storage Setup for Historical Legislation PDFs")
    print("=" * 80)
    print()

    # Create container
    container_client = create_container()

    print()

    # Test upload
    test_url = test_upload()

    print()
    print("=" * 80)
    print("Setup Complete!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Use LegislationPDFDownloader to download and upload PDFs to Azure Blob")
    print("2. Use LegislationPDFProcessor with Azure Blob URLs for OpenAI processing")
    print()
