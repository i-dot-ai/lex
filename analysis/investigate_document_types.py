"""Investigate document type distribution by year."""

from base_analyzer import BaseAnalyzer
from collections import defaultdict
import re


class DocumentTypeInvestigator(BaseAnalyzer):
    """Investigate what types of documents were processed in each year."""
    
    def __init__(self):
        super().__init__()
    
    def get_type_distribution_by_year(self):
        """Get document type distribution for each year."""
        
        # Query for all parsed legislation
        query = {
            "query": {
                "match": {"message": "Parsed legislation"}
            }
        }
        
        logs = self.search_logs(query, size=10000)
        
        # Count by year and type
        year_type_counts = defaultdict(lambda: defaultdict(int))
        
        for log in logs:
            msg = log.get("message", "")
            
            # Extract year and type
            year = self.extract_year_from_message(msg)
            leg_type = self.extract_type_from_message(msg)
            
            if year and leg_type:
                year_type_counts[year][leg_type] += 1
        
        return dict(year_type_counts)
    
    def analyze_scraping_patterns(self):
        """Analyze the scraping URLs to understand the pattern."""
        
        # Get scraping logs
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "Scraping"}},
                        {"match": {"message": "legislation.gov.uk"}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "asc"}}]
        }
        
        logs = self.search_logs(query, size=1000)
        
        # Extract and analyze URLs
        url_patterns = {
            "browse_pages": [],
            "individual_docs": [],
            "other": []
        }
        
        for log in logs:
            msg = log.get("message", "")
            url_match = re.search(r'Scraping\s+(https?://[^\s]+)', msg)
            
            if url_match:
                url = url_match.group(1)
                
                if "/browse/" in url:
                    url_patterns["browse_pages"].append(url)
                elif re.search(r'/\d{4}/\d+', url):
                    url_patterns["individual_docs"].append(url)
                else:
                    url_patterns["other"].append(url)
        
        return url_patterns
    
    def check_limit_reached(self):
        """Check if we hit the document limit."""
        
        # Count total documents
        query = {
            "query": {
                "match": {"message": "Parsed legislation"}
            }
        }
        
        result = self.es.count(index=self.index_name, body=query)
        total_parsed = result.get("count", 0)
        
        # Check for limit in logs
        limit_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "limit"}},
                        {"term": {"level": "INFO"}}
                    ]
                }
            }
        }
        
        limit_logs = self.search_logs(limit_query, size=10)
        
        return total_parsed, limit_logs
    
    def print_report(self):
        """Print investigation report."""
        print("=" * 80)
        print("DOCUMENT TYPE DISTRIBUTION INVESTIGATION")
        print("=" * 80)
        
        # Type distribution by year
        distribution = self.get_type_distribution_by_year()
        
        print("\n" + "-" * 60)
        print("DOCUMENT TYPES BY YEAR")
        print("-" * 60)
        
        # Focus on key years
        key_years = [1963, 1970, 1971, 1972, 1980, 2000, 2023, 2024]
        
        for year in key_years:
            if year in distribution:
                print(f"\n{year}:")
                total = sum(distribution[year].values())
                for dtype, count in sorted(distribution[year].items(), 
                                          key=lambda x: x[1], reverse=True):
                    pct = (count / total * 100) if total > 0 else 0
                    print(f"  {dtype:<10} {count:>5} ({pct:>5.1f}%)")
        
        # Check total counts
        print("\n" + "-" * 60)
        print("DOCUMENT TOTALS")
        print("-" * 60)
        
        total_parsed, limit_logs = self.check_limit_reached()
        print(f"\nTotal documents parsed: {total_parsed:,}")
        
        if limit_logs:
            print("\nLimit-related log entries found:")
            for log in limit_logs[:3]:
                print(f"  {log.get('message', '')[:100]}...")
        
        # Analyze scraping patterns
        print("\n" + "-" * 60)
        print("SCRAPING PATTERNS")
        print("-" * 60)
        
        patterns = self.analyze_scraping_patterns()
        print(f"\nBrowse pages scraped: {len(patterns['browse_pages'])}")
        print(f"Individual documents: {len(patterns['individual_docs'])}")
        print(f"Other URLs: {len(patterns['other'])}")
        
        if patterns['browse_pages']:
            print("\nSample browse URLs:")
            for url in patterns['browse_pages'][:3]:
                print(f"  {url}")
        
        # Analysis
        print("\n" + "=" * 80)
        print("ANALYSIS")
        print("=" * 80)
        
        print("\nKey findings:")
        print("1. The pipeline DID process documents from 1963-2025")
        print("2. The volume drops dramatically after 1971")
        print("3. This suggests the scraper found fewer documents for years 1972+")
        
        # Check if specific types were requested
        all_types = set()
        for year_data in distribution.values():
            all_types.update(year_data.keys())
        
        print(f"\nDocument types found: {', '.join(sorted(all_types))}")
        
        if "ukpga" in all_types and "uksi" not in all_types:
            print("\n⚠️  WARNING: Only ukpga documents found, no uksi!")
            print("   The pipeline might have been run with --types ukpga only")


if __name__ == "__main__":
    investigator = DocumentTypeInvestigator()
    if investigator.test_connection():
        investigator.print_report()