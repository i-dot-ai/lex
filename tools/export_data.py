#!/usr/bin/env python
"""Export utility for Elasticsearch data to various formats."""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def export_to_parquet(
    index_name: str,
    output_dir: str = "data/exports",
    es_host: str = "localhost:9200",
    batch_size: int = 10000,
    chunk_size: int = 100000,
) -> Path:
    """Export an Elasticsearch index to Parquet format.

    Args:
        index_name: Name of the index to export
        output_dir: Directory to save the export
        es_host: Elasticsearch host
        batch_size: Documents per batch from ES
        chunk_size: Documents per Parquet file

    Returns:
        Path to the output directory containing Parquet files
    """
    es = Elasticsearch([f"http://{es_host}"])

    if not es.ping():
        raise ConnectionError(f"Cannot connect to Elasticsearch at {es_host}")

    output_path = Path(output_dir) / index_name
    output_path.mkdir(parents=True, exist_ok=True)

    # Get total document count
    total_docs = es.count(index=index_name)["count"]
    logger.info(f"Exporting {total_docs:,} documents from {index_name}")

    # Scan and export in chunks
    docs = []
    chunk_num = 0

    for doc in tqdm(
        scan(es, index=index_name, size=batch_size, scroll="5m"),
        total=total_docs,
        desc=f"Exporting {index_name}",
    ):
        docs.append(doc["_source"])

        if len(docs) >= chunk_size:
            # Write chunk to Parquet
            df = pd.DataFrame(docs)
            table = pa.Table.from_pandas(df)
            pq.write_table(
                table,
                output_path / f"chunk_{chunk_num:04d}.parquet",
                compression="snappy",
            )
            logger.info(f"Wrote chunk {chunk_num} ({len(docs):,} documents)")
            docs = []
            chunk_num += 1

    # Write remaining documents
    if docs:
        df = pd.DataFrame(docs)
        table = pa.Table.from_pandas(df)
        pq.write_table(
            table,
            output_path / f"chunk_{chunk_num:04d}.parquet",
            compression="snappy",
        )
        logger.info(f"Wrote final chunk {chunk_num} ({len(docs):,} documents)")

    logger.info(f"Export complete: {output_path}")
    return output_path


def export_to_jsonl(
    index_name: str,
    output_dir: str = "data/exports",
    es_host: str = "localhost:9200",
    batch_size: int = 10000,
) -> Path:
    """Export an Elasticsearch index to JSONL format.

    Args:
        index_name: Name of the index to export
        output_dir: Directory to save the export
        es_host: Elasticsearch host
        batch_size: Documents per batch from ES

    Returns:
        Path to the output file
    """
    es = Elasticsearch([f"http://{es_host}"])

    if not es.ping():
        raise ConnectionError(f"Cannot connect to Elasticsearch at {es_host}")

    output_path = Path(output_dir) / f"{index_name}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get total document count
    total_docs = es.count(index=index_name)["count"]
    logger.info(f"Exporting {total_docs:,} documents from {index_name}")

    # Scan and export
    with open(output_path, "w") as f:
        for doc in tqdm(
            scan(es, index=index_name, size=batch_size, scroll="5m"),
            total=total_docs,
            desc=f"Exporting {index_name}",
        ):
            f.write(json.dumps(doc["_source"]) + "\n")

    logger.info(f"Export complete: {output_path}")
    return output_path


def list_indices(pattern: str = "lex-dev-*", es_host: str = "localhost:9200"):
    """List all indices matching a pattern.

    Args:
        pattern: Index name pattern
        es_host: Elasticsearch host
    """
    es = Elasticsearch([f"http://{es_host}"])

    if not es.ping():
        raise ConnectionError(f"Cannot connect to Elasticsearch at {es_host}")

    indices = es.indices.get(index=pattern)

    print(f"\nIndices matching '{pattern}':")
    print("-" * 50)

    for index_name in sorted(indices.keys()):
        count = es.count(index=index_name)["count"]
        print(f"{index_name}: {count:,} documents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Elasticsearch data")
    parser.add_argument(
        "action",
        choices=["list", "export"],
        help="Action to perform",
    )
    parser.add_argument(
        "--index",
        help="Index name to export (for export action)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "jsonl"],
        default="parquet",
        help="Export format (default: parquet)",
    )
    parser.add_argument(
        "--pattern",
        default="lex-dev-*",
        help="Index pattern for list action (default: lex-dev-*)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/exports",
        help="Output directory (default: data/exports)",
    )
    parser.add_argument(
        "--host",
        default="localhost:9200",
        help="Elasticsearch host (default: localhost:9200)",
    )

    args = parser.parse_args()

    if args.action == "list":
        list_indices(args.pattern, args.host)
    elif args.action == "export":
        if not args.index:
            print("Error: --index required for export action")
            exit(1)

        if args.format == "parquet":
            export_to_parquet(args.index, args.output_dir, args.host)
        else:
            export_to_jsonl(args.index, args.output_dir, args.host)
