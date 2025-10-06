#!/usr/bin/env python3
"""
Export individual Elasticsearch indices to Parquet files with better error handling.
"""

import sys
import time
from pathlib import Path
from export_to_parquet import ElasticsearchToParquetExporter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_index_with_retry(index_name: str, output_dir: str = "./parquet_exports", 
                           batch_size: int = 2000, chunk_size: int = 50000, 
                           max_retries: int = 3):
    """Export a single index with retry logic."""
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} to export {index_name}")
            
            # Create exporter with smaller batch size for large indices
            if 'caselaw' in index_name:
                # Caselaw has very large documents, use smaller batch
                batch_size = 500
                chunk_size = 10000
            
            exporter = ElasticsearchToParquetExporter(
                es_host="localhost:9200",
                batch_size=batch_size
            )
            
            # Create output directory with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir = Path(output_dir) / timestamp / index_name.replace("lex-dev-", "")
            
            # Export the index
            files = exporter.export_index_to_parquet(
                index_name, 
                export_dir, 
                chunk_size=chunk_size
            )
            
            logger.info(f"Successfully exported {index_name} to {len(files)} file(s)")
            return True
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for {index_name}: {e}")
            if attempt < max_retries - 1:
                wait_time = 30 * (attempt + 1)  # Progressive backoff
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to export {index_name} after {max_retries} attempts")
                return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Export individual Elasticsearch index to Parquet")
    parser.add_argument("index", help="Index name to export")
    parser.add_argument("--output-dir", default="./parquet_exports", help="Output directory")
    parser.add_argument("--batch-size", type=int, default=2000, help="Batch size for scrolling")
    parser.add_argument("--chunk-size", type=int, default=50000, help="Documents per Parquet file")
    
    args = parser.parse_args()
    
    success = export_index_with_retry(
        args.index, 
        args.output_dir, 
        args.batch_size, 
        args.chunk_size
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()