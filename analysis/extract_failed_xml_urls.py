"""Extract URLs of XML documents that failed to parse properly."""

from typing import Dict, List, Set
from collections import defaultdict
from datetime import datetime
from base_analyzer import BaseAnalyzer
import json
import re


class FailedXMLURLExtractor(BaseAnalyzer):
    """Extract URLs of XML documents that encountered parsing errors."""
    
    def __init__(self):
        super().__init__()
        
    def extract_url_from_message(self, message: str) -> str:
        """Extract legislation.gov.uk URL from log message."""
        # Look for legislation.gov.uk URLs
        url_pattern = r'https?://(?:www\.)?legislation\.gov\.uk/[^\s]+'
        match = re.search(url_pattern, message)
        if match:
            return match.group(0).rstrip('.,;)')
        
        # Also try to construct URL from ID if present
        id_pattern = r'http://www\.legislation\.gov\.uk/id/([^/]+)/(\d{4})/(\d+)'
        id_match = re.search(id_pattern, message)
        if id_match:
            leg_type, year, number = id_match.groups()
            return f"https://www.legislation.gov.uk/{leg_type}/{year}/{number}"
        
        return None
    
    def get_failed_xml_urls(self) -> Dict[str, List[Dict]]:
        """Get all URLs where XML parsing failed (excluding PDF fallbacks)."""
        
        # Query for XML parsing errors that are NOT PDF fallbacks
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"level": "ERROR"}},
                        {"match": {"message": "Error parsing"}}
                    ],
                    "must_not": [
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group URLs by error type
        failed_urls = defaultdict(list)
        
        for log in logs:
            message = log.get("message", "")
            exception = log.get("exception", "")
            timestamp = log.get("timestamp", "")
            
            url = self.extract_url_from_message(message)
            if url:
                # Categorize the error
                error_category = "unknown"
                if "metadata is missing" in message:
                    error_category = "missing_metadata"
                elif "ParseError" in str(exception):
                    error_category = "xml_parse_error"
                elif "UnicodeDecodeError" in str(exception):
                    error_category = "encoding_error"
                elif "AttributeError" in str(exception):
                    error_category = "attribute_error"
                
                failed_urls[error_category].append({
                    "url": url,
                    "timestamp": timestamp,
                    "error_message": message[:200],
                    "exception_snippet": str(exception)[:200] if exception else None
                })
        
        # Deduplicate URLs within each category
        for category in failed_urls:
            seen_urls = set()
            unique_entries = []
            for entry in failed_urls[category]:
                if entry["url"] not in seen_urls:
                    seen_urls.add(entry["url"])
                    unique_entries.append(entry)
            failed_urls[category] = unique_entries
        
        return dict(failed_urls)
    
    def get_pdf_fallback_urls(self) -> Dict[str, List[str]]:
        """Get URLs where we had to fall back to PDF (no XML body)."""
        
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"message": "likely a pdf"}},
                        {"match": {"message": "no body found"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query)
        
        # Group by year
        pdf_urls_by_year = defaultdict(set)
        
        for log in logs:
            message = log.get("message", "")
            url = self.extract_url_from_message(message)
            year = self.extract_year_from_message(message)
            
            if url and year:
                pdf_urls_by_year[year].add(url)
        
        # Convert sets to sorted lists
        result = {}
        for year in sorted(pdf_urls_by_year.keys()):
            result[str(year)] = sorted(list(pdf_urls_by_year[year]))
        
        return result
    
    def get_successful_xml_urls_sample(self, limit: int = 100) -> List[str]:
        """Get a sample of successfully parsed XML URLs for comparison."""
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"level": "INFO"}},
                        {"match": {"message": "Parsed legislation"}}
                    ]
                }
            }
        }
        
        logs = self.search_logs(query, size=limit)
        
        urls = []
        for log in logs:
            message = log.get("message", "")
            url = self.extract_url_from_message(message)
            if url:
                urls.append(url)
        
        return urls
    
    def analyze_error_patterns(self) -> Dict[str, any]:
        """Analyze patterns in XML parsing failures."""
        
        failed_urls = self.get_failed_xml_urls()
        
        # Analyze by year and type
        year_stats = defaultdict(lambda: defaultdict(int))
        type_stats = defaultdict(lambda: defaultdict(int))
        
        for error_type, entries in failed_urls.items():
            for entry in entries:
                url = entry["url"]
                
                # Extract year
                year_match = re.search(r'/(\d{4})/', url)
                if year_match:
                    year = int(year_match.group(1))
                    year_stats[year][error_type] += 1
                
                # Extract type
                type_match = re.search(r'legislation\.gov\.uk/([^/]+)/', url)
                if type_match:
                    leg_type = type_match.group(1)
                    type_stats[leg_type][error_type] += 1
        
        return {
            "total_failed_urls": sum(len(entries) for entries in failed_urls.values()),
            "by_error_type": {k: len(v) for k, v in failed_urls.items()},
            "by_year": dict(year_stats),
            "by_legislation_type": dict(type_stats)
        }
    
    def save_results(self):
        """Save all extracted URLs to JSON files."""
        
        # Failed XML URLs (real parsing errors)
        failed_urls = self.get_failed_xml_urls()
        with open("analysis/failed_xml_urls.json", "w") as f:
            json.dump(failed_urls, f, indent=2)
        
        # PDF fallback URLs
        pdf_urls = self.get_pdf_fallback_urls()
        with open("analysis/pdf_fallback_urls.json", "w") as f:
            json.dump(pdf_urls, f, indent=2)
        
        # Sample of successful URLs
        success_sample = self.get_successful_xml_urls_sample()
        with open("analysis/successful_xml_urls_sample.json", "w") as f:
            json.dump(success_sample, f, indent=2)
        
        # Error analysis
        analysis = self.analyze_error_patterns()
        with open("analysis/xml_error_analysis.json", "w") as f:
            json.dump(analysis, f, indent=2)
        
        return failed_urls, pdf_urls, analysis
    
    def print_report(self):
        """Print a report of failed XML URLs."""
        print("=" * 80)
        print("FAILED XML URL EXTRACTION REPORT")
        print("=" * 80)
        
        failed_urls, pdf_urls, analysis = self.save_results()
        
        # Summary statistics
        print(f"\nTotal unique failed XML URLs: {analysis['total_failed_urls']}")
        print(f"Total PDF fallback documents: {sum(len(urls) for urls in pdf_urls.values())}")
        
        # Failed XML by error type
        print("\n" + "-" * 60)
        print("FAILED XML URLS BY ERROR TYPE")
        print("-" * 60)
        
        for error_type, count in analysis['by_error_type'].items():
            print(f"{error_type:<25} {count:>5} URLs")
            # Show first 3 examples
            if error_type in failed_urls and failed_urls[error_type]:
                for i, entry in enumerate(failed_urls[error_type][:3]):
                    print(f"  → {entry['url']}")
                if count > 3:
                    print(f"  ... and {count - 3} more")
        
        # PDF fallbacks by year
        print("\n" + "-" * 60)
        print("PDF FALLBACK DOCUMENTS BY YEAR")
        print("-" * 60)
        
        for year in sorted(pdf_urls.keys())[-10:]:  # Last 10 years
            count = len(pdf_urls[year])
            print(f"{year}: {count:>5} documents")
        
        # Error patterns
        print("\n" + "-" * 60)
        print("XML PARSING ERROR PATTERNS")
        print("-" * 60)
        
        if analysis['by_year']:
            print("\nErrors by year (last 5 years with errors):")
            years_with_errors = sorted(analysis['by_year'].keys())[-5:]
            for year in years_with_errors:
                print(f"  {year}: {sum(analysis['by_year'][year].values())} errors")
        
        if analysis['by_legislation_type']:
            print("\nErrors by legislation type:")
            for leg_type, errors in sorted(analysis['by_legislation_type'].items()):
                total = sum(errors.values())
                print(f"  {leg_type:<10} {total:>3} errors")
        
        print("\n" + "=" * 80)
        print("Detailed results saved to:")
        print("  - analysis/failed_xml_urls.json (XML parsing errors)")
        print("  - analysis/pdf_fallback_urls.json (PDF-only documents)")
        print("  - analysis/successful_xml_urls_sample.json (Working examples)")
        print("  - analysis/xml_error_analysis.json (Error pattern analysis)")


if __name__ == "__main__":
    extractor = FailedXMLURLExtractor()
    if extractor.test_connection():
        extractor.print_report()