#!/usr/bin/env python3
"""
Export Elasticsearch indices to Parquet files for LLM fine-tuning.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from elasticsearch import Elasticsearch
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ElasticsearchToParquetExporter:
    """Export Elasticsearch indices to Parquet files."""
    
    def __init__(self, es_host: str = "localhost:9200", batch_size: int = 10000):
        """Initialize the exporter.
        
        Args:
            es_host: Elasticsearch host and port
            batch_size: Number of documents to fetch per batch
        """
        self.es = Elasticsearch([f"http://{es_host}"])
        self.batch_size = batch_size
        
        # Verify connection
        if not self.es.ping():
            raise ConnectionError(f"Cannot connect to Elasticsearch at {es_host}")
        
        logger.info(f"Connected to Elasticsearch at {es_host}")
    
    def get_indices(self, pattern: str = "lex-dev-*") -> List[str]:
        """Get list of indices matching pattern.
        
        Args:
            pattern: Index pattern to match
            
        Returns:
            List of index names
        """
        indices = self.es.indices.get(index=pattern)
        return list(indices.keys())
    
    def scroll_index(self, index_name: str) -> Iterator[Dict]:
        """Scroll through all documents in an index.
        
        Args:
            index_name: Name of the index to scroll
            
        Yields:
            Documents from the index
        """
        # Initial search
        response = self.es.search(
            index=index_name,
            body={
                "size": self.batch_size,
                "query": {"match_all": {}}
            },
            scroll="2m"  # Keep scroll context alive for 2 minutes
        )
        
        scroll_id = response["_scroll_id"]
        hits = response["hits"]["hits"]
        
        # Yield initial batch
        for hit in hits:
            doc = hit["_source"]
            doc["_id"] = hit["_id"]
            doc["_index"] = hit["_index"]
            yield doc
        
        # Continue scrolling
        while len(hits) > 0:
            response = self.es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = response["_scroll_id"]
            hits = response["hits"]["hits"]
            
            for hit in hits:
                doc = hit["_source"]
                doc["_id"] = hit["_id"]
                doc["_index"] = hit["_index"]
                yield doc
        
        # Clear scroll context
        self.es.clear_scroll(scroll_id=scroll_id)
    
    def export_index_to_parquet(
        self, 
        index_name: str, 
        output_dir: Path,
        chunk_size: int = 100000
    ) -> List[Path]:
        """Export a single index to Parquet files.
        
        Args:
            index_name: Name of the index to export
            output_dir: Directory to save Parquet files
            chunk_size: Number of documents per Parquet file
            
        Returns:
            List of created Parquet file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get total document count
        count_response = self.es.count(index=index_name)
        total_docs = count_response["count"]
        logger.info(f"Exporting {total_docs:,} documents from {index_name}")
        
        # Clean index name for filename
        clean_index_name = index_name.replace("lex-dev-", "")
        
        documents = []
        chunk_num = 0
        output_files = []
        
        with tqdm(total=total_docs, desc=f"Exporting {index_name}") as pbar:
            for doc in self.scroll_index(index_name):
                documents.append(doc)
                pbar.update(1)
                
                if len(documents) >= chunk_size:
                    # Save chunk to Parquet
                    output_file = output_dir / f"{clean_index_name}_chunk_{chunk_num:04d}.parquet"
                    self._save_to_parquet(documents, output_file)
                    output_files.append(output_file)
                    
                    logger.info(f"Saved {len(documents):,} documents to {output_file}")
                    documents = []
                    chunk_num += 1
        
        # Save remaining documents
        if documents:
            output_file = output_dir / f"{clean_index_name}_chunk_{chunk_num:04d}.parquet"
            self._save_to_parquet(documents, output_file)
            output_files.append(output_file)
            logger.info(f"Saved {len(documents):,} documents to {output_file}")
        
        return output_files
    
    def _save_to_parquet(self, documents: List[Dict], output_file: Path):
        """Save documents to a Parquet file.
        
        Args:
            documents: List of documents to save
            output_file: Path to save the Parquet file
        """
        # Flatten nested structures for better compatibility
        flattened_docs = []
        for doc in documents:
            flat_doc = self._flatten_document(doc)
            flattened_docs.append(flat_doc)
        
        # Convert to DataFrame
        df = pd.DataFrame(flattened_docs)
        
        # Handle any remaining complex types by converting to JSON strings
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if column contains non-string objects
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if sample and (isinstance(sample, (dict, list))):
                    df[col] = df[col].apply(lambda x: json.dumps(x) if x is not None else None)
        
        # Save to Parquet with compression
        df.to_parquet(output_file, compression='snappy', index=False)
    
    def _flatten_document(self, doc: Dict, prefix: str = "") -> Dict:
        """Flatten nested document structure.
        
        Args:
            doc: Document to flatten
            prefix: Prefix for nested keys
            
        Returns:
            Flattened document
        """
        flattened = {}
        
        for key, value in doc.items():
            new_key = f"{prefix}{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recurse for nested dicts, but limit depth
                if prefix.count("_") < 2:  # Limit nesting depth
                    flattened.update(self._flatten_document(value, f"{new_key}_"))
                else:
                    flattened[new_key] = json.dumps(value)
            elif isinstance(value, list):
                # Convert lists to JSON strings for compatibility
                flattened[new_key] = json.dumps(value)
            else:
                flattened[new_key] = value
        
        return flattened
    
    def export_all_indices(
        self, 
        output_dir: Path = Path("./parquet_exports"),
        pattern: str = "lex-dev-*"
    ) -> Dict[str, List[Path]]:
        """Export all matching indices to Parquet files.
        
        Args:
            output_dir: Base directory for exports
            pattern: Pattern to match indices
            
        Returns:
            Dictionary mapping index names to list of output files
        """
        output_dir = Path(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = output_dir / timestamp
        export_dir.mkdir(parents=True, exist_ok=True)
        
        indices = self.get_indices(pattern)
        logger.info(f"Found {len(indices)} indices to export: {indices}")
        
        results = {}
        
        for index_name in indices:
            try:
                index_dir = export_dir / index_name.replace("lex-dev-", "")
                output_files = self.export_index_to_parquet(index_name, index_dir)
                results[index_name] = output_files
                logger.info(f"Successfully exported {index_name} to {len(output_files)} file(s)")
            except Exception as e:
                logger.error(f"Failed to export {index_name}: {e}")
                results[index_name] = []
        
        # Save metadata
        metadata = {
            "export_timestamp": timestamp,
            "indices": {
                index: {
                    "files": [str(f) for f in files],
                    "file_count": len(files)
                }
                for index, files in results.items()
            }
        }
        
        metadata_file = export_dir / "export_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Export complete! Files saved to {export_dir}")
        logger.info(f"Metadata saved to {metadata_file}")
        
        return results


def main():
    """Main function to run the export."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Export Elasticsearch indices to Parquet files")
    parser.add_argument(
        "--host", 
        default="localhost:9200",
        help="Elasticsearch host and port (default: localhost:9200)"
    )
    parser.add_argument(
        "--pattern",
        default="lex-dev-*",
        help="Index pattern to export (default: lex-dev-*)"
    )
    parser.add_argument(
        "--output-dir",
        default="./parquet_exports",
        help="Output directory for Parquet files (default: ./parquet_exports)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for scrolling (default: 10000)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100000,
        help="Documents per Parquet file (default: 100000)"
    )
    parser.add_argument(
        "--index",
        help="Export only a specific index"
    )
    
    args = parser.parse_args()
    
    # Initialize exporter
    exporter = ElasticsearchToParquetExporter(
        es_host=args.host,
        batch_size=args.batch_size
    )
    
    # Export indices
    if args.index:
        # Export single index
        output_dir = Path(args.output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
        index_dir = output_dir / args.index.replace("lex-dev-", "")
        files = exporter.export_index_to_parquet(
            args.index, 
            index_dir, 
            chunk_size=args.chunk_size
        )
        logger.info(f"Exported {args.index} to {len(files)} file(s)")
    else:
        # Export all matching indices
        results = exporter.export_all_indices(
            output_dir=Path(args.output_dir),
            pattern=args.pattern
        )
        
        # Print summary
        print("\n" + "="*50)
        print("EXPORT SUMMARY")
        print("="*50)
        for index, files in results.items():
            print(f"{index}: {len(files)} file(s)")
        print("="*50)


if __name__ == "__main__":
    main()