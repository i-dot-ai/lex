"""Find and analyze failed documents from pipeline logs."""

from base_analyzer import BaseAnalyzer
from datetime import datetime
import json


class FailedDocumentsFinder(BaseAnalyzer):
    """Find and analyze documents that failed during processing."""
    
    def __init__(self):
        super().__init__()
    
    def find_failed_documents(self, start_time=None, end_time=None):
        """Find all documents that failed to process."""
        
        # Build query
        must_clauses = [
            {"exists": {"field": "error_type"}},
            {"exists": {"field": "doc_id"}}
        ]
        
        # Add time range if specified
        if start_time or end_time:
            time_range = {}
            if start_time:
                time_range["gte"] = start_time
            if end_time:
                time_range["lte"] = end_time
            must_clauses.append({"range": {"timestamp": time_range}})
        
        query = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "aggs": {
                "error_types": {
                    "terms": {
                        "field": "error_type.keyword",
                        "size": 50
                    }
                },
                "doc_types": {
                    "terms": {
                        "field": "doc_type.keyword",
                        "size": 50
                    }
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        return self.search_logs(query, size=1000)
    
    def find_validation_errors(self):
        """Find documents with validation errors."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"error_type": "ValidationError"}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        return self.search_logs(query, size=100)
    
    def find_commentary_citation_errors(self):
        """Find CommentaryCitation validation errors."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "CommentaryCitation"}},
                        {"match": {"message": "validation error"}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        return self.search_logs(query, size=100)
    
    def get_failed_document_summary(self, logs):
        """Create summary of failed documents."""
        
        summary = {
            "total_failures": len(logs),
            "by_error_type": {},
            "by_doc_type": {},
            "sample_failures": []
        }
        
        for log in logs:
            # Count by error type
            error_type = log.get("error_type", "unknown")
            summary["by_error_type"][error_type] = summary["by_error_type"].get(error_type, 0) + 1
            
            # Count by doc type
            doc_type = log.get("doc_type", "unknown")
            summary["by_doc_type"][doc_type] = summary["by_doc_type"].get(doc_type, 0) + 1
            
            # Collect samples
            if len(summary["sample_failures"]) < 10:
                summary["sample_failures"].append({
                    "timestamp": log.get("timestamp"),
                    "doc_id": log.get("doc_id"),
                    "error_type": error_type,
                    "message": log.get("message", "")[:200]
                })
        
        return summary
    
    def print_report(self, start_time=None, end_time=None):
        """Print comprehensive failed documents report."""
        print("=" * 80)
        print("FAILED DOCUMENTS ANALYSIS")
        print("=" * 80)
        
        # Find failed documents
        failed_logs = self.find_failed_documents(start_time, end_time)
        
        if not failed_logs:
            print("\nNo failed documents found in the specified time range.")
            return
        
        # Get summary
        summary = self.get_failed_document_summary(failed_logs)
        
        print(f"\nTotal Failed Documents: {summary['total_failures']}")
        
        # Error types breakdown
        print("\nFailures by Error Type:")
        print("-" * 40)
        for error_type, count in sorted(summary["by_error_type"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count}")
        
        # Document types breakdown
        if summary["by_doc_type"]:
            print("\nFailures by Document Type:")
            print("-" * 40)
            for doc_type, count in sorted(summary["by_doc_type"].items(), key=lambda x: x[1], reverse=True):
                print(f"  {doc_type}: {count}")
        
        # Sample failures
        print("\nSample Failed Documents:")
        print("-" * 80)
        for failure in summary["sample_failures"]:
            print(f"\nTime: {failure['timestamp']}")
            print(f"Doc ID: {failure['doc_id']}")
            print(f"Error: {failure['error_type']}")
            print(f"Message: {failure['message']}")
        
        # Check for CommentaryCitation errors specifically
        print("\n" + "-" * 80)
        print("COMMENTARY CITATION ERRORS")
        print("-" * 80)
        
        citation_errors = self.find_commentary_citation_errors()
        if citation_errors:
            print(f"\nFound {len(citation_errors)} CommentaryCitation errors")
            for i, log in enumerate(citation_errors[:5]):
                print(f"\n{i+1}. {log.get('timestamp', 'N/A')}")
                print(f"   Message: {log.get('message', '')[:150]}")
        else:
            print("\nNo CommentaryCitation errors found")
        
        # Save detailed results
        output_file = "failed_documents_analysis.json"
        with open(output_file, "w") as f:
            json.dump({
                "summary": summary,
                "citation_errors_count": len(citation_errors),
                "query_time": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    finder = FailedDocumentsFinder()
    if finder.test_connection():
        # Analyze last 24 hours by default
        from datetime import timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        finder.print_report(
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )