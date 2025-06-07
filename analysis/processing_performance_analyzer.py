"""Analyze processing performance metrics from pipeline logs."""

from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from base_analyzer import BaseAnalyzer
import json
import re


class ProcessingPerformanceAnalyzer(BaseAnalyzer):
    """Analyze processing speed, batch sizes, and throughput."""
    
    def __init__(self):
        super().__init__()
    
    def get_processing_throughput(self) -> Dict[str, any]:
        """Calculate document processing throughput over time."""
        
        # Query for successful processing logs
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Uploaded batch"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Extract batch sizes and calculate throughput
        hourly_stats = defaultdict(lambda: {"batches": 0, "documents": 0})
        
        for log in logs:
            message = log.get("message", "")
            timestamp = log.get("timestamp", "")
            
            # Extract batch size from message like "Uploaded batch of 50 documents"
            batch_match = re.search(r'batch of (\d+) documents', message)
            if batch_match and timestamp:
                batch_size = int(batch_match.group(1))
                
                # Round timestamp to hour
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hour_key = dt.strftime("%Y-%m-%d %H:00")
                    
                    hourly_stats[hour_key]["batches"] += 1
                    hourly_stats[hour_key]["documents"] += batch_size
                except:
                    pass
        
        # Calculate average throughput
        total_docs = sum(stats["documents"] for stats in hourly_stats.values())
        total_hours = len(hourly_stats)
        avg_throughput = total_docs / total_hours if total_hours > 0 else 0
        
        # Find peak hour
        peak_hour = max(hourly_stats.items(), 
                       key=lambda x: x[1]["documents"]) if hourly_stats else (None, {"documents": 0})
        
        return {
            "total_documents_processed": total_docs,
            "total_hours_active": total_hours,
            "average_documents_per_hour": round(avg_throughput, 2),
            "peak_hour": peak_hour[0],
            "peak_hour_documents": peak_hour[1]["documents"],
            "hourly_breakdown": dict(sorted(hourly_stats.items()))
        }
    
    def get_processing_time_by_type(self) -> Dict[str, Dict]:
        """Analyze processing time patterns by document type."""
        
        # Query for processing start/end patterns
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "Starting pipeline"}},
                        {"match": {"message": "Pipeline completed"}},
                        {"match": {"message": "Processing"}},
                        {"match": {"message": "Parsing"}},
                        {"match": {"message": "Scraping"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by document type and track timing
        doc_type_stats = defaultdict(lambda: {
            "parse_times": [],
            "scrape_times": [],
            "total_documents": 0
        })
        
        # Simple heuristic: track time between related log entries
        last_action = {}
        
        for log in logs:
            message = log.get("message", "")
            timestamp = log.get("timestamp", "")
            
            # Identify document type
            doc_type = None
            if "legislation" in message.lower():
                doc_type = "legislation"
            elif "caselaw" in message.lower():
                doc_type = "caselaw"
            elif "amendment" in message.lower():
                doc_type = "amendment"
            elif "explanatory" in message.lower():
                doc_type = "explanatory_note"
            
            if doc_type and timestamp:
                if "Parsed" in message:
                    doc_type_stats[doc_type]["total_documents"] += 1
        
        return dict(doc_type_stats)
    
    def get_batch_size_analysis(self) -> Dict[str, any]:
        """Analyze batch size patterns and efficiency."""
        
        query = {
            "query": {
                "match": {"message": "batch of"}
            }
        }
        
        logs = self.search_logs(query)
        
        batch_sizes = []
        batch_size_distribution = defaultdict(int)
        
        for log in logs:
            message = log.get("message", "")
            batch_match = re.search(r'batch of (\d+)', message)
            if batch_match:
                size = int(batch_match.group(1))
                batch_sizes.append(size)
                batch_size_distribution[size] += 1
        
        if batch_sizes:
            return {
                "total_batches": len(batch_sizes),
                "average_batch_size": round(sum(batch_sizes) / len(batch_sizes), 2),
                "min_batch_size": min(batch_sizes),
                "max_batch_size": max(batch_sizes),
                "common_batch_sizes": dict(sorted(
                    batch_size_distribution.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5])
            }
        else:
            return {
                "total_batches": 0,
                "average_batch_size": 0,
                "min_batch_size": 0,
                "max_batch_size": 0,
                "common_batch_sizes": {}
            }
    
    def get_memory_usage_patterns(self) -> Dict[str, any]:
        """Look for memory-related issues and garbage collection patterns."""
        
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "memory"}},
                        {"match": {"message": "MemoryError"}},
                        {"match": {"message": "gc.collect"}},
                        {"match": {"message": "batch"}},
                        {"match": {"message": "Force garbage collection"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        memory_events = []
        gc_events = 0
        memory_errors = 0
        
        for log in logs:
            message = log.get("message", "")
            level = log.get("level", "")
            timestamp = log.get("timestamp", "")
            
            if "MemoryError" in message or ("memory" in message.lower() and level == "ERROR"):
                memory_errors += 1
            
            if "gc.collect" in message or "garbage collection" in message.lower():
                gc_events += 1
            
            memory_events.append({
                "timestamp": timestamp,
                "message": message[:200],
                "level": level
            })
        
        return {
            "total_memory_related_logs": len(memory_events),
            "memory_errors": memory_errors,
            "garbage_collection_events": gc_events,
            "recent_events": memory_events[-10:]  # Last 10 events
        }
    
    def print_report(self):
        """Print a comprehensive performance analysis report."""
        print("=" * 80)
        print("PROCESSING PERFORMANCE ANALYSIS REPORT")
        print("=" * 80)
        
        # Throughput analysis
        print("\n" + "-" * 60)
        print("DOCUMENT PROCESSING THROUGHPUT")
        print("-" * 60)
        
        throughput = self.get_processing_throughput()
        print(f"Total documents processed: {throughput['total_documents_processed']:,}")
        print(f"Total active hours: {throughput['total_hours_active']}")
        print(f"Average documents/hour: {throughput['average_documents_per_hour']:,.2f}")
        print(f"Peak hour: {throughput['peak_hour']} ({throughput['peak_hour_documents']:,} documents)")
        
        # Batch size analysis
        print("\n" + "-" * 60)
        print("BATCH SIZE ANALYSIS")
        print("-" * 60)
        
        batch_analysis = self.get_batch_size_analysis()
        print(f"Total batches: {batch_analysis['total_batches']:,}")
        print(f"Average batch size: {batch_analysis['average_batch_size']}")
        print(f"Batch size range: {batch_analysis['min_batch_size']} - {batch_analysis['max_batch_size']}")
        
        if batch_analysis['common_batch_sizes']:
            print("\nMost common batch sizes:")
            for size, count in list(batch_analysis['common_batch_sizes'].items())[:5]:
                print(f"  Size {size}: {count:,} occurrences")
        
        # Memory usage patterns
        print("\n" + "-" * 60)
        print("MEMORY USAGE PATTERNS")
        print("-" * 60)
        
        memory_analysis = self.get_memory_usage_patterns()
        print(f"Memory-related log entries: {memory_analysis['total_memory_related_logs']}")
        print(f"Memory errors: {memory_analysis['memory_errors']}")
        print(f"Garbage collection events: {memory_analysis['garbage_collection_events']}")
        
        # Processing by type
        print("\n" + "-" * 60)
        print("DOCUMENTS PROCESSED BY TYPE")
        print("-" * 60)
        
        by_type = self.get_processing_time_by_type()
        print(f"{'Document Type':<20} {'Documents Processed':<20}")
        print("-" * 60)
        
        for doc_type, stats in sorted(by_type.items()):
            print(f"{doc_type:<20} {stats['total_documents']:<20,}")
        
        # Save detailed results
        results = {
            "summary": {
                "analysis_timestamp": datetime.now().isoformat()
            },
            "throughput": throughput,
            "batch_analysis": batch_analysis,
            "memory_analysis": memory_analysis,
            "documents_by_type": by_type
        }
        
        with open("analysis/performance_report.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print("\n" + "=" * 80)
        print("Detailed results saved to: analysis/performance_report.json")


if __name__ == "__main__":
    analyzer = ProcessingPerformanceAnalyzer()
    if analyzer.test_connection():
        analyzer.print_report()