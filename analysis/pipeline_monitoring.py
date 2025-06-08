"""Comprehensive pipeline monitoring and status analysis tool."""

from base_analyzer import BaseAnalyzer
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re
import json


class PipelineMonitor(BaseAnalyzer):
    """Monitor pipeline execution, progress, and logging quality."""
    
    def check_pipeline_status(self, hours_back=None):
        """Check current pipeline status and recent execution patterns."""
        
        print("=" * 80)
        print("PIPELINE STATUS CHECK")
        print("=" * 80)
        
        if hours_back:
            print(f"Analyzing last {hours_back} hours of pipeline activity\n")
        else:
            print("Analyzing all-time pipeline activity\n")
        
        # Check for pipeline completion messages
        completion_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "Pipeline processing complete"}}
                    ]
                }
            },
            "size": 10,
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        # Add time filter if specified
        if hours_back:
            completion_query["query"]["bool"]["filter"] = {
                "range": {
                    "timestamp": {
                        "gte": f"now-{hours_back}h"
                    }
                }
            }
        
        completions = self.search_logs(completion_query)
        
        if completions:
            print(f"Found {len(completions)} pipeline completions:")
            for comp in completions:
                timestamp = comp.get("timestamp", "")
                model = comp.get("model", "unknown")
                total_docs = comp.get("total_documents", 0)
                duration_min = comp.get("duration_minutes", 0)
                status = comp.get("final_status", "unknown")
                
                print(f"\n  {timestamp}")
                print(f"    Model: {model}")
                print(f"    Documents: {total_docs:,}")
                print(f"    Duration: {duration_min:.1f} minutes")
                print(f"    Status: {status}")
        else:
            print("No pipeline completions found in the specified timeframe.")
        
        # Check for active pipelines
        self._check_active_pipelines(hours_back)
        
        # Check for errors or interruptions
        self._check_pipeline_errors(hours_back)
    
    def _check_active_pipelines(self, hours_back):
        """Check for currently active pipeline runs."""
        
        # Look for pipeline starts without corresponding completions
        start_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "Pipeline starting"}}
                    ]
                }
            },
            "size": 10,
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        # Add time filter if specified
        if hours_back:
            start_query["query"]["bool"]["filter"] = {
                "range": {
                    "timestamp": {
                        "gte": f"now-{hours_back}h"
                    }
                }
            }
        
        starts = self.search_logs(start_query)
        
        if starts:
            print(f"\n\nPipeline starts in last {hours_back} hours:")
            for start in starts[:5]:
                timestamp = start.get("timestamp", "")
                params = start.get("pipeline_params", {})
                print(f"\n  {timestamp}")
                if params:
                    print(f"    Model: {params.get('model', 'N/A')}")
                    print(f"    Years: {params.get('years', 'N/A')}")
    
    def _check_pipeline_errors(self, hours_back):
        """Check for pipeline errors or interruptions."""
        
        error_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"level": "ERROR"}},
                        {"match_phrase": {"message": "Pipeline"}}
                    ]
                }
            },
            "size": 20
        }
        
        # Add time filter if specified
        if hours_back:
            error_query["query"]["bool"]["filter"] = {
                "range": {
                    "timestamp": {
                        "gte": f"now-{hours_back}h"
                    }
                }
            }
        
        errors = self.search_logs(error_query)
        
        if errors:
            print(f"\n\nPipeline errors found: {len(errors)}")
            error_types = Counter()
            for error in errors:
                msg = error.get("message", "")
                if "rate limit" in msg.lower():
                    error_types["Rate Limited"] += 1
                elif "failed" in msg.lower():
                    error_types["Failed"] += 1
                else:
                    error_types["Other"] += 1
            
            for error_type, count in error_types.most_common():
                print(f"  {error_type}: {count}")
    
    def check_structured_logging(self, hours_back=1):
        """Verify structured logging fields are working correctly."""
        
        print("\n\n" + "="*80)
        print("STRUCTURED LOGGING CHECK")
        print("="*80)
        
        # Sample recent logs
        sample_query = {
            "query": {
                "bool": {
                    "filter": {
                        "range": {
                            "timestamp": {
                                "gte": f"now-{hours_back}h"
                            }
                        }
                    }
                }
            },
            "size": 100,
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        logs = self.search_logs(sample_query)
        
        # Check for structured fields
        field_presence = defaultdict(int)
        structured_fields = [
            'service', 'environment', 'hostname', 'doc_id', 'doc_type', 
            'doc_year', 'doc_number', 'error_type', 'processing_status',
            'batch_size', 'total_documents', 'duration_minutes'
        ]
        
        for log in logs:
            for field in structured_fields:
                if field in log and log[field] is not None:
                    field_presence[field] += 1
        
        print(f"\nStructured field presence (out of {len(logs)} logs):")
        for field in structured_fields:
            count = field_presence[field]
            percentage = (count / len(logs) * 100) if logs else 0
            if count > 0:
                print(f"  {field:<20} {count:>4} ({percentage:>5.1f}%)")
    
    def check_progress_tracking(self, hours_back=None):
        """Check pipeline progress tracking and throughput."""
        
        print("\n\n" + "="*80)
        print("PROGRESS TRACKING ANALYSIS")
        print("="*80)
        
        # Look for progress update messages
        progress_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "Progress update"}}
                    ]
                }
            },
            "size": 100,
            "sort": [{"timestamp": {"order": "asc"}}]
        }
        
        # Add time filter if specified
        if hours_back:
            progress_query["query"]["bool"]["filter"] = {
                "range": {
                    "timestamp": {
                        "gte": f"now-{hours_back}h"
                    }
                }
            }
        
        progress_logs = self.search_logs(progress_query)
        
        if progress_logs:
            print(f"\nFound {len(progress_logs)} progress updates")
            
            # Extract metrics
            throughput_rates = []
            for log in progress_logs:
                msg = log.get("message", "")
                # Extract rate from message like "10.5 docs/second"
                rate_match = re.search(r'(\d+\.?\d*)\s*docs/second', msg)
                if rate_match:
                    throughput_rates.append(float(rate_match.group(1)))
            
            if throughput_rates:
                avg_rate = sum(throughput_rates) / len(throughput_rates)
                min_rate = min(throughput_rates)
                max_rate = max(throughput_rates)
                
                print(f"\nThroughput statistics:")
                print(f"  Average: {avg_rate:.1f} docs/second")
                print(f"  Min: {min_rate:.1f} docs/second")
                print(f"  Max: {max_rate:.1f} docs/second")
        
        # Check batch upload logs
        self._check_batch_uploads(hours_back)
    
    def _check_batch_uploads(self, hours_back):
        """Check batch upload patterns."""
        
        batch_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match_phrase": {"message": "Uploaded batch"}}
                    ]
                }
            },
            "size": 1000
        }
        
        # Add time filter if specified
        if hours_back:
            batch_query["query"]["bool"]["filter"] = {
                "range": {
                    "timestamp": {
                        "gte": f"now-{hours_back}h"
                    }
                }
            }
        
        batches = self.search_logs(batch_query)
        
        if batches:
            batch_sizes = []
            for batch in batches:
                msg = batch.get("message", "")
                # Extract batch size from message
                size_match = re.search(r'batch of (\d+) documents', msg)
                if size_match:
                    batch_sizes.append(int(size_match.group(1)))
            
            if batch_sizes:
                print(f"\n\nBatch upload statistics ({len(batch_sizes)} batches):")
                print(f"  Average size: {sum(batch_sizes)/len(batch_sizes):.1f}")
                print(f"  Min size: {min(batch_sizes)}")
                print(f"  Max size: {max(batch_sizes)}")
    
    def generate_summary_report(self, hours_back=None):
        """Generate a comprehensive summary report."""
        
        print("\n\n" + "="*80)
        print("PIPELINE MONITORING SUMMARY")
        print("="*80)
        print(f"Report generated: {datetime.now().isoformat()}")
        if hours_back:
            print(f"Analysis window: Last {hours_back} hours")
        else:
            print("Analysis window: All-time data")
        
        # Run all checks
        self.check_pipeline_status(hours_back)
        self.check_structured_logging(hours_back=1)  # Keep recent for structured logging
        self.check_progress_tracking(hours_back)
        
        print("\n" + "="*80)
        print("END OF REPORT")
        print("="*80)


if __name__ == "__main__":
    import sys
    
    monitor = PipelineMonitor()
    if monitor.test_connection():
        # Check if hours parameter provided
        hours = None  # Default to all-time
        if len(sys.argv) > 1:
            try:
                hours = int(sys.argv[1])
            except ValueError:
                print(f"Invalid hours parameter: {sys.argv[1]}, using all-time data")
        
        monitor.generate_summary_report(hours_back=hours)