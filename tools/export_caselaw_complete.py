#!/usr/bin/env python3
"""
Export caselaw from Elasticsearch with extended scroll timeout and fallback pagination.
"""

import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch, exceptions
import logging
from tqdm import tqdm
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CaselawExporter:
    def __init__(self, es_host="http://localhost:9200"):
        self.es = Elasticsearch(
            hosts=[es_host],
            request_timeout=60,
            max_retries=3,
            retry_on_timeout=True
        )
        
    def export_with_scroll(self, index_name, output_dir, batch_size=500, chunk_size=10000):
        """Export using scroll API with 30 minute timeout."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get total count
        count_response = self.es.count(index=index_name)
        total_docs = count_response['count']
        logger.info(f"Exporting {total_docs} documents from {index_name}")
        
        # Initialize scroll with 30 minute timeout
        response = self.es.search(
            index=index_name,
            scroll='30m',  # 30 minute scroll timeout
            size=batch_size,
            body={"query": {"match_all": {}}}
        )
        
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        
        all_docs = []
        chunk_num = 0
        
        with tqdm(total=total_docs, desc=f"Exporting {index_name}") as pbar:
            while hits:
                # Process batch
                for hit in hits:
                    doc = hit['_source']
                    doc['_id'] = hit['_id']
                    all_docs.append(doc)
                    pbar.update(1)
                
                # Save chunk if needed
                if len(all_docs) >= chunk_size:
                    self._save_chunk(all_docs[:chunk_size], output_dir, index_name.replace('lex-dev-', ''), chunk_num)
                    all_docs = all_docs[chunk_size:]
                    chunk_num += 1
                
                # Get next batch with extended timeout
                try:
                    response = self.es.scroll(scroll_id=scroll_id, scroll='30m')
                    hits = response['hits']['hits']
                except exceptions.NotFoundError:
                    logger.warning("Scroll context lost, switching to pagination")
                    # Continue from where we left off using pagination
                    return self.export_with_pagination(index_name, output_dir, 
                                                      start_from=pbar.n, 
                                                      chunk_num=chunk_num,
                                                      existing_docs=all_docs)
        
        # Save remaining documents
        if all_docs:
            self._save_chunk(all_docs, output_dir, index_name.replace('lex-dev-', ''), chunk_num)
        
        # Clear scroll context
        try:
            self.es.clear_scroll(scroll_id=scroll_id)
        except:
            pass
            
        return chunk_num + 1
    
    def export_with_pagination(self, index_name, output_dir, start_from=0, chunk_num=0, existing_docs=None):
        """Fallback export using search_after pagination."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get total count
        count_response = self.es.count(index=index_name)
        total_docs = count_response['count']
        logger.info(f"Using pagination from document {start_from}/{total_docs}")
        
        all_docs = existing_docs or []
        batch_size = 500
        last_sort = None
        
        with tqdm(total=total_docs, initial=start_from, desc=f"Exporting {index_name}") as pbar:
            while pbar.n < total_docs:
                # Build query with search_after
                body = {
                    "query": {"match_all": {}},
                    "size": batch_size,
                    "sort": [{"_id": "asc"}]
                }
                
                if last_sort:
                    body["search_after"] = last_sort
                
                response = self.es.search(index=index_name, body=body)
                hits = response['hits']['hits']
                
                if not hits:
                    break
                
                for hit in hits:
                    doc = hit['_source']
                    doc['_id'] = hit['_id']
                    all_docs.append(doc)
                    pbar.update(1)
                
                # Save chunk if needed
                if len(all_docs) >= 10000:
                    self._save_chunk(all_docs[:10000], output_dir, index_name.replace('lex-dev-', ''), chunk_num)
                    all_docs = all_docs[10000:]
                    chunk_num += 1
                
                # Update last_sort for next iteration
                last_sort = hits[-1]['sort']
                
                # Small delay to avoid overwhelming ES
                time.sleep(0.1)
        
        # Save remaining documents
        if all_docs:
            self._save_chunk(all_docs, output_dir, index_name.replace('lex-dev-', ''), chunk_num)
            chunk_num += 1
            
        return chunk_num
    
    def _save_chunk(self, docs, output_dir, index_type, chunk_num):
        """Save a chunk of documents to Parquet."""
        df = pd.json_normalize(docs)
        
        # Create output path
        output_file = output_dir / f"{index_type}_chunk_{chunk_num:04d}.parquet"
        
        # Save to Parquet
        df.to_parquet(output_file, compression='snappy', index=False)
        logger.info(f"Saved {len(docs)} documents to {output_file}")

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"parquet_exports/complete_caselaw_{timestamp}")
    
    exporter = CaselawExporter()
    
    try:
        num_chunks = exporter.export_with_scroll("lex-dev-caselaw", output_dir)
        logger.info(f"Successfully exported caselaw to {num_chunks} files")
        return 0
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())