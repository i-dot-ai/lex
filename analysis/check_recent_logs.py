"""Check recent pipeline logs to see all the structured logging enhancements."""

from base_analyzer import BaseAnalyzer
from datetime import datetime
import json


class RecentLogsChecker(BaseAnalyzer):
    """Check recent logs for all structured logging features."""
    
    def __init__(self):
        super().__init__()
    
    def get_pipeline_parameter_logs(self):
        """Get logs showing pipeline parameters."""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Pipeline"}},
                        {"range": {"timestamp": {"gte": "now-2h"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": 20
        }
        
        response = self.es.search(index=self.index_name, body=query)
        
        parameter_logs = []
        for hit in response.get("hits", {}).get("hits", []):
            log = hit["_source"]
            if "parameter" in log.get("message", "").lower() or "starting" in log.get("message", "").lower():
                parameter_logs.append(log)
        
        return parameter_logs
    
    def get_progress_logs(self):
        """Get progress update logs."""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Progress update"}},
                        {"range": {"timestamp": {"gte": "now-2h"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": 10
        }
        
        response = self.es.search(index=self.index_name, body=query)
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]
    
    def get_summary_statistics(self):
        """Get summary statistics of recent processing."""
        query = {
            "query": {
                "range": {"timestamp": {"gte": "now-2h"}}
            },
            "aggs": {
                "by_level": {
                    "terms": {"field": "level.keyword"}
                },
                "by_status": {
                    "terms": {"field": "processing_status.keyword"}
                },
                "by_type": {
                    "terms": {"field": "doc_type.keyword"}
                },
                "has_doc_id": {
                    "filter": {"exists": {"field": "doc_id"}}
                },
                "by_year": {
                    "terms": {"field": "doc_year", "size": 20}
                }
            },
            "size": 0
        }
        
        response = self.es.search(index=self.index_name, body=query)
        return response.get("aggregations", {})
    
    def get_successful_parse_samples(self):
        """Get samples of successful parses with structured data."""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"processing_status.keyword": "success"}},
                        {"range": {"timestamp": {"gte": "now-2h"}}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": 5
        }
        
        response = self.es.search(index=self.index_name, body=query)
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]
    
    def print_report(self):
        """Print comprehensive recent logs report."""
        print("=" * 80)
        print("RECENT PIPELINE LOGS ANALYSIS")
        print(f"Time: {datetime.now().isoformat()}")
        print("=" * 80)
        
        # Get statistics
        stats = self.get_summary_statistics()
        
        print("\n" + "-" * 60)
        print("SUMMARY STATISTICS (Last 2 hours)")
        print("-" * 60)
        
        total_logs = stats.get("has_doc_id", {}).get("doc_count", 0)
        print(f"\nTotal logs with document metadata: {total_logs}")
        
        if stats.get("by_level"):
            print("\nLog levels:")
            for bucket in stats["by_level"]["buckets"]:
                print(f"  {bucket['key']}: {bucket['doc_count']}")
        
        if stats.get("by_status"):
            print("\nProcessing status:")
            for bucket in stats["by_status"]["buckets"]:
                pct = (bucket['doc_count'] / total_logs * 100) if total_logs > 0 else 0
                print(f"  {bucket['key']}: {bucket['doc_count']} ({pct:.1f}%)")
        
        if stats.get("by_type"):
            print("\nDocument types:")
            for bucket in stats["by_type"]["buckets"]:
                print(f"  {bucket['key']}: {bucket['doc_count']}")
        
        if stats.get("by_year"):
            print("\nDocuments by year:")
            for bucket in sorted(stats["by_year"]["buckets"], key=lambda x: x["key"]):
                print(f"  {bucket['key']}: {bucket['doc_count']}")
        
        # Pipeline parameters
        print("\n" + "-" * 60)
        print("PIPELINE PARAMETER LOGS")
        print("-" * 60)
        
        param_logs = self.get_pipeline_parameter_logs()
        if param_logs:
            for log in param_logs[:3]:
                print(f"\n{log.get('timestamp', '')[:19]}: {log.get('message', '')}")
                # Check for structured pipeline_params
                if 'pipeline_params' in log:
                    print("  Structured parameters found:")
                    for k, v in log['pipeline_params'].items():
                        print(f"    {k}: {v}")
        else:
            print("No pipeline parameter logs found")
        
        # Progress logs
        print("\n" + "-" * 60)
        print("PROGRESS UPDATES")
        print("-" * 60)
        
        progress_logs = self.get_progress_logs()
        if progress_logs:
            for log in progress_logs[:3]:
                print(f"{log.get('timestamp', '')[:19]}: {log.get('message', '')}")
        else:
            print("No progress logs found yet")
        
        # Successful parse samples
        print("\n" + "-" * 60)
        print("SUCCESSFUL PARSE SAMPLES")
        print("-" * 60)
        
        success_logs = self.get_successful_parse_samples()
        if success_logs:
            for log in success_logs[:2]:
                print(f"\nTimestamp: {log.get('timestamp', '')[:19]}")
                print(f"Message: {log.get('message', '')[:80]}...")
                print(f"Doc ID: {log.get('doc_id', 'N/A')}")
                print(f"Type: {log.get('doc_type', 'N/A')}, Year: {log.get('doc_year', 'N/A')}")
                print(f"Title: {log.get('title', 'N/A')}")
        else:
            print("No successful parses found yet")
        
        print("\n" + "=" * 80)


if __name__ == "__main__":
    checker = RecentLogsChecker()
    if checker.test_connection():
        checker.print_report()