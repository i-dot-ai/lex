"""Run all analysis scripts and generate a comprehensive report."""

import sys
import os
from datetime import datetime

# Add the analysis directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xml_completeness_analyzer import XMLCompletenessAnalyzer
from error_type_analyzer import ErrorTypeAnalyzer
from processing_performance_analyzer import ProcessingPerformanceAnalyzer
from explanatory_notes_analyzer import ExplanatoryNotesAnalyzer
from extract_failed_xml_urls import FailedXMLURLExtractor


def main():
    """Run all analyses and generate reports."""
    print("=" * 80)
    print("LEX PIPELINE COMPREHENSIVE ANALYSIS")
    print(f"Analysis started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Test connection first
    print("\nTesting Elasticsearch connection...")
    test_analyzer = XMLCompletenessAnalyzer()
    if not test_analyzer.test_connection():
        print("Failed to connect to Elasticsearch. Exiting.")
        return
    
    print("\nConnection successful. Starting analyses...\n")
    
    # Run each analysis
    analyses = [
        ("XML Completeness Analysis", XMLCompletenessAnalyzer),
        ("Error Type Analysis", ErrorTypeAnalyzer),
        ("Processing Performance Analysis", ProcessingPerformanceAnalyzer),
        ("Explanatory Notes Coverage Analysis", ExplanatoryNotesAnalyzer),
        ("Failed XML URL Extraction", FailedXMLURLExtractor)
    ]
    
    for name, analyzer_class in analyses:
        print(f"\n{'='*80}")
        print(f"Running {name}...")
        print(f"{'='*80}")
        
        try:
            analyzer = analyzer_class()
            analyzer.print_report()
        except Exception as e:
            print(f"Error running {name}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("ALL ANALYSES COMPLETE")
    print(f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    print("\nGenerated reports:")
    print("  - analysis/xml_completeness_report.json")
    print("  - analysis/error_type_report.json")
    print("  - analysis/performance_report.json")
    print("  - analysis/explanatory_notes_report.json")
    print("  - analysis/failed_xml_urls.json")
    print("  - analysis/pdf_fallback_urls.json")
    print("  - analysis/xml_error_analysis.json")


if __name__ == "__main__":
    main()