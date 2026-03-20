#!/usr/bin/env python
"""
Bulk export Qdrant collections to Parquet files in Azure Blob Storage.

This script exports Qdrant collections to Snappy-compressed Parquet files,
with a clean nested folder structure for easy navigation.

Output structure:
    downloads/
    ├── latest/                         # Current exports (stable URLs)
    │   ├── legislation.parquet
    │   ├── legislation_section/
    │   │   ├── 1801.parquet
    │   │   └── ...
    │   ├── explanatory_note.parquet
    │   ├── amendment.parquet
    │   └── manifest.json
    └── archive/                        # Historical exports
        └── 2024-12-01/
            └── (same structure)

Collections:
- legislation (~220K docs) - Single file
- legislation_section (~2M docs) - Split by year
- explanatory_note (~82K docs) - Single file
- amendment (~892K docs) - Single file

Usage:
    # Run in Azure Container Apps Job (default: dry run)
    python scripts/bulk_export_parquet.py

    # Actually upload to blob storage
    USE_CLOUD_QDRANT=true uv run python scripts/bulk_export_parquet.py --apply

    # Export specific collection
    USE_CLOUD_QDRANT=true uv run python scripts/bulk_export_parquet.py \
        --apply --collection legislation
"""

import argparse
import gc
import json
import logging
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src and scripts to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from _console import console, print_header, print_summary, setup_logging  # noqa: E402
from azure.storage.blob import BlobServiceClient, ContentSettings  # noqa: E402
from qdrant_client.models import FieldCondition, Filter, MatchValue  # noqa: E402

from lex.core.qdrant_client import get_qdrant_client  # noqa: E402
from lex.settings import (  # noqa: E402
    AMENDMENT_COLLECTION,
    # CASELAW_COLLECTION,  # disabled
    # CASELAW_SECTION_COLLECTION,  # disabled
    # CASELAW_SUMMARY_COLLECTION,  # disabled
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logger = logging.getLogger(__name__)

# Collection configurations
# batch_size tuned for memory: large text fields need smaller batches
COLLECTIONS = {
    LEGISLATION_COLLECTION: {
        "split_by_year": False,
        "year_field": None,
        "batch_size": 2000,
    },
    LEGISLATION_SECTION_COLLECTION: {
        "split_by_year": True,
        "year_field": "legislation_year",
        "batch_size": 500,  # Smaller: sections have large text
    },
    # Caselaw collections disabled
    # CASELAW_COLLECTION: {
    #     "split_by_year": False,
    #     "year_field": None,
    #     "batch_size": 100,
    # },
    # CASELAW_SECTION_COLLECTION: {
    #     "split_by_year": True,
    #     "year_field": "year",
    #     "batch_size": 500,
    # },
    # CASELAW_SUMMARY_COLLECTION: {
    #     "split_by_year": False,
    #     "year_field": None,
    #     "batch_size": 2000,
    # },
    EXPLANATORY_NOTE_COLLECTION: {
        "split_by_year": False,
        "year_field": None,
        "batch_size": 1000,
    },
    AMENDMENT_COLLECTION: {
        "split_by_year": False,
        "year_field": None,
        "batch_size": 2000,
    },
}

# Retention period for archive
RETENTION_WEEKS = 4

# Retry configuration for Qdrant Cloud timeouts
MAX_RETRIES = 5
BASE_BACKOFF = 2.0


def _is_retryable(error: Exception) -> bool:
    """Check if an error is a retryable timeout/connection issue."""
    error_str = str(error).lower()
    return any(term in error_str for term in ["timed out", "timeout", "connection", "disconnected"])


def _retry_with_backoff(operation_name: str, operation, max_retries=MAX_RETRIES):
    """Execute an operation with exponential backoff retry for timeout errors."""
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt == max_retries - 1 or not _is_retryable(e):
                raise
            backoff = BASE_BACKOFF * (2**attempt)
            logger.warning(
                f"{operation_name} timeout (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {backoff:.0f}s..."
            )
            time.sleep(backoff)


def get_blob_service_client() -> BlobServiceClient:
    """Get Azure Blob Storage client."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable not set")
    return BlobServiceClient.from_connection_string(connection_string)


def scroll_collection_batched(
    qdrant_client,
    collection_name: str,
    batch_size: int = 500,
    year_filter: int | None = None,
    year_field: str | None = None,
):
    """Scroll through collection yielding batches (memory-efficient generator)."""
    offset = None
    batch_num = 0
    total_records = 0

    # Build filter if year specified
    scroll_filter = None
    if year_filter is not None and year_field:
        scroll_filter = Filter(
            must=[FieldCondition(key=year_field, match=MatchValue(value=year_filter))]
        )

    while True:
        batch_num += 1
        results, next_offset = _retry_with_backoff(
            f"scroll {collection_name} batch {batch_num}",
            lambda: qdrant_client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=scroll_filter,
            ),
        )

        if not results:
            break

        payloads = [point.payload for point in results]
        total_records += len(payloads)

        if batch_num % 20 == 0:
            logger.info(f"    Batch {batch_num}: {total_records:,} records")

        yield payloads

        offset = next_offset
        if offset is None:
            break


def infer_schema_from_sample(
    qdrant_client,
    collection_name: str,
    sample_size: int = 50,
    year_filter: int | None = None,
    year_field: str | None = None,
) -> pa.Schema:
    """Infer Arrow schema from a small sample."""
    scroll_filter = None
    if year_filter is not None and year_field:
        scroll_filter = Filter(
            must=[FieldCondition(key=year_field, match=MatchValue(value=year_filter))]
        )

    results, _ = _retry_with_backoff(
        f"schema inference {collection_name}",
        lambda: qdrant_client.scroll(
            collection_name=collection_name,
            limit=sample_size,
            with_payload=True,
            with_vectors=False,
            scroll_filter=scroll_filter,
        ),
    )

    if not results:
        raise ValueError(f"No records found for schema inference in {collection_name}")

    sample_payloads = [point.payload for point in results]
    sample_table = pa.Table.from_pylist(sample_payloads)
    schema = sample_table.schema

    # Cleanup
    del sample_table
    del sample_payloads
    gc.collect()

    return schema


def payloads_to_parquet_streaming(
    qdrant_client,
    collection_name: str,
    output_path: Path,
    batch_size: int = 500,
    year_filter: int | None = None,
    year_field: str | None = None,
) -> int:
    """
    Stream records to Parquet using ParquetWriter (memory-efficient).

    Memory usage: O(batch_size) instead of O(total records).
    """
    # Infer schema from filtered sample for consistency
    schema = infer_schema_from_sample(
        qdrant_client,
        collection_name,
        sample_size=50,
        year_filter=year_filter,
        year_field=year_field,
    )

    total_records = 0
    writer = None

    try:
        for batch_payloads in scroll_collection_batched(
            qdrant_client,
            collection_name,
            batch_size=batch_size,
            year_filter=year_filter,
            year_field=year_field,
        ):
            if not batch_payloads:
                continue

            # Convert batch to Arrow table with consistent schema
            try:
                batch_table = pa.Table.from_pylist(batch_payloads, schema=schema)
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                # Schema mismatch — field absent from sample, re-infer and unify
                batch_table = pa.Table.from_pylist(batch_payloads)
                schema = pa.unify_schemas([schema, batch_table.schema])
                batch_table = batch_table.cast(schema)

            # Initialise writer on first batch
            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    schema=batch_table.schema,
                    compression="snappy",
                    version="2.6",
                )

            # Write batch incrementally
            writer.write_table(batch_table)
            total_records += len(batch_payloads)

            # Explicit cleanup after each batch
            del batch_table
            del batch_payloads
            gc.collect()

    finally:
        if writer:
            writer.close()

    return total_records


def upload_to_blob(
    blob_service_client: BlobServiceClient,
    container_name: str,
    local_path: Path,
    blob_name: str,
    dry_run: bool = False,
) -> str:
    """Upload file to Azure Blob Storage."""
    if dry_run:
        logger.info(f"    [DRY RUN] Would upload -> {blob_name}")
        return f"https://example.blob.core.windows.net/{container_name}/{blob_name}"

    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)

    def _upload():
        with open(local_path, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/vnd.apache.parquet"),
            )

    _retry_with_backoff(f"upload {blob_name}", _upload)

    return blob_client.url


def get_years_in_collection(qdrant_client, collection_name: str, year_field: str) -> list[int]:
    """Get distinct years by sampling records with minimal payload.

    Samples 10K records (year field only) to discover year range, then generates
    the full range. Much faster than scrolling 2M+ records.
    """
    results, _ = _retry_with_backoff(
        f"year discovery {collection_name}",
        lambda: qdrant_client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=[year_field],
            with_vectors=False,
        ),
    )

    years = set()
    for point in results:
        year = point.payload.get(year_field)
        if year is not None:
            years.add(int(year))

    if not years:
        logger.warning(f"No years found in {collection_name} (sampled {len(results)} records)")
        return []

    # Fill range between min/max — empty years are skipped during export
    min_year = min(years)
    max_year = max(years)
    logger.info(f"  Year sample: {len(years)} distinct years from {len(results)} records")
    return list(range(min_year, max_year + 1))


def export_collection(
    qdrant_client,
    blob_service_client: BlobServiceClient | None,
    collection_name: str,
    config: dict,
    container_name: str,
    date_str: str,
    dry_run: bool = False,
) -> dict:
    """Export a single collection to Parquet files."""
    console.rule(f"Exporting: {collection_name}")

    batch_size = config.get("batch_size", 500)
    logger.info(f"  Batch size: {batch_size}")

    stats = {
        "collection": collection_name,
        "files": [],
        "total_records": 0,
        "total_bytes": 0,
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        if config["split_by_year"]:
            # Export by year
            years = get_years_in_collection(qdrant_client, collection_name, config["year_field"])
            year_range = f"{min(years)} - {max(years)}" if years else "none"
            logger.info(f"  Found years: {year_range} ({len(years)} years)")

            for year in years:
                logger.info(f"\n  Year {year}...")

                filename = f"{year}.parquet"
                local_path = temp_path / filename

                try:
                    record_count = payloads_to_parquet_streaming(
                        qdrant_client,
                        collection_name,
                        local_path,
                        batch_size=batch_size,
                        year_filter=year,
                        year_field=config["year_field"],
                    )
                except ValueError as e:
                    logger.info(f"    Skipping year {year}: {e}")
                    continue

                if record_count == 0:
                    logger.info(f"    No records for year {year}")
                    continue

                file_size = local_path.stat().st_size
                size_mb = file_size / 1024 / 1024
                logger.info(f"    {record_count:,} records, {size_mb:.1f} MB")

                if blob_service_client:
                    # Upload to archive
                    archive_blob = f"archive/{date_str}/{collection_name}/{year}.parquet"
                    upload_to_blob(
                        blob_service_client, container_name, local_path, archive_blob, dry_run
                    )

                    # Upload to latest
                    latest_blob = f"latest/{collection_name}/{year}.parquet"
                    url = upload_to_blob(
                        blob_service_client, container_name, local_path, latest_blob, dry_run
                    )

                    stats["files"].append(
                        {
                            "name": f"{collection_name}/{year}.parquet",
                            "url": url,
                            "records": record_count,
                            "bytes": file_size,
                            "year": year,
                        }
                    )

                stats["total_records"] += record_count
                stats["total_bytes"] += file_size

                # Cleanup between years
                gc.collect()

        else:
            # Single file export
            logger.info("  Streaming to Parquet...")

            filename = f"{collection_name}.parquet"
            local_path = temp_path / filename

            record_count = payloads_to_parquet_streaming(
                qdrant_client,
                collection_name,
                local_path,
                batch_size=batch_size,
            )

            if record_count == 0:
                logger.warning(f"  No records in {collection_name}")
                return stats

            file_size = local_path.stat().st_size
            logger.info(f"  Total: {record_count:,} records, {file_size / 1024 / 1024:.1f} MB")

            if blob_service_client:
                # Upload to archive
                archive_blob = f"archive/{date_str}/{collection_name}.parquet"
                upload_to_blob(
                    blob_service_client, container_name, local_path, archive_blob, dry_run
                )

                # Upload to latest
                latest_blob = f"latest/{collection_name}.parquet"
                url = upload_to_blob(
                    blob_service_client, container_name, local_path, latest_blob, dry_run
                )

                stats["files"].append(
                    {
                        "name": f"{collection_name}.parquet",
                        "url": url,
                        "records": record_count,
                        "bytes": file_size,
                    }
                )

            stats["total_records"] = record_count
            stats["total_bytes"] = file_size

    return stats


def cleanup_old_exports(
    blob_service_client: BlobServiceClient,
    container_name: str,
    retention_weeks: int = RETENTION_WEEKS,
    dry_run: bool = False,
) -> int:
    """Delete archive exports older than retention period."""
    console.rule(f"Cleaning up archives older than {retention_weeks} weeks")

    cutoff_date = datetime.now(timezone.utc) - timedelta(weeks=retention_weeks)
    deleted_count = 0

    container_client = blob_service_client.get_container_client(container_name)

    for blob in container_client.list_blobs(name_starts_with="archive/"):
        # Check if blob is older than cutoff
        if blob.last_modified and blob.last_modified < cutoff_date:
            if dry_run:
                logger.info(f"  [DRY RUN] Would delete: {blob.name}")
            else:
                container_client.delete_blob(blob.name)
                logger.info(f"  Deleted: {blob.name}")
            deleted_count += 1

    logger.info(f"  Cleaned up {deleted_count} old files")
    return deleted_count


def generate_manifest(
    blob_service_client: BlobServiceClient | None,
    container_name: str,
    all_stats: list[dict],
    date_str: str,
    base_url: str,
    dry_run: bool = False,
) -> None:
    """Generate and upload manifest.json."""
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "export_date": date_str,
        "base_url": base_url,
        "collections": {},
        "totals": {
            "total_records": sum(s["total_records"] for s in all_stats),
            "total_bytes": sum(s["total_bytes"] for s in all_stats),
            "total_files": sum(len(s["files"]) for s in all_stats),
        },
    }

    for stats in all_stats:
        manifest["collections"][stats["collection"]] = {
            "total_records": stats["total_records"],
            "total_bytes": stats["total_bytes"],
            "files": stats["files"],
        }

    manifest_json = json.dumps(manifest, indent=2)

    if dry_run:
        logger.info("\n[DRY RUN] Would upload latest/manifest.json")
        return

    if blob_service_client:
        container_client = blob_service_client.get_container_client(container_name)

        # Upload to archive
        archive_blob = f"archive/{date_str}/manifest.json"
        blob_client = container_client.get_blob_client(archive_blob)
        blob_client.upload_blob(
            manifest_json,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )

        # Upload to latest
        latest_blob = "latest/manifest.json"
        blob_client = container_client.get_blob_client(latest_blob)
        blob_client.upload_blob(
            manifest_json,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )

        logger.info(f"\n  Uploaded manifest: {latest_blob}")


def main() -> bool:
    """Run bulk export. Returns True if at least one collection exported successfully."""
    parser = argparse.ArgumentParser(description="Export Qdrant collections to Parquet")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default: dry run)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        choices=list(COLLECTIONS.keys()),
        help="Export only a specific collection",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup of old exports",
    )
    args = parser.parse_args()

    setup_logging()

    print_header(
        "Bulk Export to Parquet",
        mode="APPLY" if args.apply else "DRY RUN",
        details={"Collection": args.collection or "all"},
    )

    # Initialise clients
    qdrant_client = get_qdrant_client()

    blob_service_client = None
    if args.apply:
        try:
            blob_service_client = get_blob_service_client()
        except ValueError as e:
            logger.error(f"Cannot connect to blob storage: {e}")
            logger.info("Running in dry-run mode")
            args.apply = False

    container_name = os.environ.get("BULK_DOWNLOAD_CONTAINER", "downloads")
    base_url = os.environ.get(
        "DOWNLOADS_BASE_URL", f"https://lexdownloads.blob.core.windows.net/{container_name}"
    )
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Filter collections if specified
    collections_to_export = COLLECTIONS
    if args.collection:
        collections_to_export = {args.collection: COLLECTIONS[args.collection]}

    # Export each collection
    all_stats = []
    for collection_name, config in collections_to_export.items():
        try:
            stats = export_collection(
                qdrant_client,
                blob_service_client,
                collection_name,
                config,
                container_name,
                date_str,
                dry_run=not args.apply,
            )
            all_stats.append(stats)

            # Force garbage collection between collections
            gc.collect()

        except Exception as e:
            logger.error(f"Failed to export {collection_name}: {e}")
            traceback.print_exc()
            all_stats.append(
                {
                    "collection": collection_name,
                    "files": [],
                    "total_records": 0,
                    "total_bytes": 0,
                    "error": str(e),
                }
            )

    # Update manifest only for full exports that succeeded
    total_exported = sum(s["total_records"] for s in all_stats)
    if args.collection:
        logger.info("Single-collection export — skipping manifest update")
    elif total_exported > 0:
        generate_manifest(
            blob_service_client,
            container_name,
            all_stats,
            date_str,
            base_url,
            dry_run=not args.apply,
        )
    else:
        logger.warning("All collections failed to export — manifest NOT updated")

    # Cleanup old exports (only when at least one collection succeeded)
    if total_exported > 0 and blob_service_client and not args.no_cleanup and args.apply:
        cleanup_old_exports(
            blob_service_client,
            container_name,
            retention_weeks=RETENTION_WEEKS,
            dry_run=not args.apply,
        )

    # Summary
    total_records = sum(s["total_records"] for s in all_stats)
    total_bytes = sum(s["total_bytes"] for s in all_stats)
    total_files = sum(len(s["files"]) for s in all_stats)

    summary_stats = {
        "Collections": str(len(all_stats)),
        "Files": str(total_files),
        "Records": f"{total_records:,}",
        "Size": f"{total_bytes / 1024 / 1024:.1f} MB",
    }
    for stats in all_stats:
        status = "OK" if stats["total_records"] > 0 else "EMPTY"
        if "error" in stats:
            status = "FAILED"
        summary_stats[stats["collection"]] = f"{stats['total_records']:,} records [{status}]"

    print_summary("Export Complete", summary_stats, success=total_records > 0)

    return total_records > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
