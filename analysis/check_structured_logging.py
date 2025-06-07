"""Check if structured logging is working in the new pipeline run."""

from base_analyzer import BaseAnalyzer
from datetime import datetime, timedelta
import json


class StructuredLoggingChecker(BaseAnalyzer):
    """Check for structured logging fields in recent logs."""
    
    def __init__(self):
        super().__init__()
    
    def check_pipeline_start_logs(self):
        """Look for pipeline start logs with parameters."""
        
        # Query for recent pipeline start logs
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Pipeline starting"}},
                        {"range": {"timestamp": {"gte": "now-1h"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        response = self.es.search(index=self.index_name, body=query, size=10)
        hits = response.get("hits", {}).get("hits", [])
        
        start_logs = []
        for hit in hits:
            log = hit["_source"]
            # Check if structured fields exist
            if "pipeline_params" in log:
                start_logs.append({
                    "timestamp": log.get("timestamp"),
                    "message": log.get("message"),
                    "pipeline_params": log.get("pipeline_params")
                })
        
        return start_logs
    
    def check_progress_logs(self):
        """Look for progress update logs."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Progress update"}},
                        {"range": {"timestamp": {"gte": "now-1h"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        response = self.es.search(index=self.index_name, body=query, size=5)
        hits = response.get("hits", {}).get("hits", [])
        
        return [hit["_source"] for hit in hits]
    
    def check_structured_document_logs(self):
        """Check for logs with structured document metadata."""
        
        # Query for logs with doc_id field
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "doc_id"}},
                        {"range": {"timestamp": {"gte": "now-30m"}}}
                    ]
                }
            },
            "aggs": {
                "by_status": {
                    "terms": {
                        "field": "processing_status.keyword"
                    }
                },
                "by_type": {
                    "terms": {
                        "field": "doc_type.keyword"
                    }
                }
            }
        }
        
        response = self.es.search(index=self.index_name, body=query, size=100)
        
        # Extract sample logs and aggregations
        sample_logs = []
        for hit in response.get("hits", {}).get("hits", [])[:5]:
            log = hit["_source"]
            sample_logs.append({
                "timestamp": log.get("timestamp"),
                "message": log.get("message", "")[:100],
                "doc_id": log.get("doc_id"),
                "doc_type": log.get("doc_type"),
                "doc_year": log.get("doc_year"),
                "processing_status": log.get("processing_status"),
                "has_xml": log.get("has_xml")
            })
        
        aggregations = {
            "total_with_doc_id": response.get("hits", {}).get("total", {}).get("value", 0),
            "by_status": {},
            "by_type": {}
        }
        
        # Process aggregations
        for bucket in response.get("aggregations", {}).get("by_status", {}).get("buckets", []):
            aggregations["by_status"][bucket["key"]] = bucket["doc_count"]
        
        for bucket in response.get("aggregations", {}).get("by_type", {}).get("buckets", []):
            aggregations["by_type"][bucket["key"]] = bucket["doc_count"]
        
        return sample_logs, aggregations
    
    def check_parameter_logging(self):
        """Check if pipeline parameters are being logged."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Pipeline parameters"}},
                        {"range": {"timestamp": {"gte": "now-1h"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        response = self.es.search(index=self.index_name, body=query, size=5)
        hits = response.get("hits", {}).get("hits", [])
        
        return [hit["_source"] for hit in hits]
    
    def print_report(self):
        """Print structured logging check report."""
        print("=" * 80)
        print("STRUCTURED LOGGING CHECK")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 80)
        
        # Check pipeline start logs
        print("\n" + "-" * 60)
        print("PIPELINE START LOGS (with structured params)")
        print("-" * 60)
        
        start_logs = self.check_pipeline_start_logs()
        if start_logs:
            for log in start_logs[:2]:
                print(f"\nTimestamp: {log['timestamp']}")
                print(f"Message: {log['message']}")
                if log.get('pipeline_params'):
                    print("Pipeline Parameters:")
                    for k, v in log['pipeline_params'].items():
                        print(f"  {k}: {v}")
        else:
            print("No pipeline start logs with structured parameters found")
        
        # Check parameter logs
        print("\n" + "-" * 60)
        print("PIPELINE PARAMETER LOGS")
        print("-" * 60)
        
        param_logs = self.check_parameter_logging()
        if param_logs:
            for log in param_logs[:2]:
                print(f"{log.get('timestamp', '')[:19]}: {log.get('message', '')}")
        else:
            print("No parameter logs found")
        
        # Check progress logs
        print("\n" + "-" * 60)
        print("PROGRESS UPDATE LOGS")
        print("-" * 60)
        
        progress_logs = self.check_progress_logs()
        if progress_logs:
            for log in progress_logs[:3]:
                print(f"{log.get('timestamp', '')[:19]}: {log.get('message', '')}")
        else:
            print("No progress logs found yet")
        
        # Check structured document logs
        print("\n" + "-" * 60)
        print("STRUCTURED DOCUMENT LOGS")
        print("-" * 60)
        
        sample_logs, aggregations = self.check_structured_document_logs()
        
        print(f"\nTotal logs with doc_id field: {aggregations['total_with_doc_id']}")
        
        if aggregations["by_status"]:
            print("\nDocuments by processing status:")
            for status, count in sorted(aggregations["by_status"].items()):
                print(f"  {status}: {count}")
        
        if aggregations["by_type"]:
            print("\nDocuments by type:")
            for doc_type, count in sorted(aggregations["by_type"].items(), 
                                        key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {doc_type}: {count}")
        
        if sample_logs:
            print("\nSample structured logs:")
            for log in sample_logs[:3]:
                print(f"\n  Timestamp: {log['timestamp']}")
                print(f"  Message: {log['message']}...")
                print(f"  doc_id: {log['doc_id']}")
                print(f"  doc_type: {log['doc_type']}")
                print(f"  doc_year: {log['doc_year']}")
                print(f"  status: {log['processing_status']}")
                print(f"  has_xml: {log['has_xml']}")
        
        print("\n" + "=" * 80)
        
        if aggregations['total_with_doc_id'] > 0:
            print("✅ STRUCTURED LOGGING IS WORKING!")
            print(f"   Found {aggregations['total_with_doc_id']} logs with structured fields")
        else:
            print("⚠️  No structured logs found yet")
            print("   The pipeline may still be starting up or not using the new code")


if __name__ == "__main__":
    checker = StructuredLoggingChecker()
    if checker.test_connection():
        checker.print_report()