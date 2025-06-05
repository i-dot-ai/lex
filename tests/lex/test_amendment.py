"""Integration tests for amendment package."""

from lex.amendment.models import Amendment
from lex.amendment.parser import AmendmentParser
from lex.amendment.scraper import AmendmentScraper


def test_amendment_integration():
    """Test the full amendment scraping and parsing pipeline."""
    # Initialize components
    scraper = AmendmentScraper()
    parser = AmendmentParser()

    # Scrape and parse content
    amendments = []
    for amendment_soup in scraper.load_content(years=[2024], limit=200):
        amendment = parser.parse_content(amendment_soup)
        amendments.extend(amendment)

    # Assertions
    assert len(amendments) > 0, "Should have parsed at least one amendment"

    # Check that each amendment has basic required attributes
    for amendment in amendments:
        assert amendment is not None
        assert isinstance(amendment, Amendment)
        assert hasattr(amendment, "changed_legislation")
        assert hasattr(amendment, "affecting_legislation")
        assert hasattr(amendment, "type_of_effect")
        assert hasattr(amendment, "id")

        # Check year is 2024 as per the query
        assert amendment.changed_year == 2024 or amendment.affecting_year == 2024

        # Check URLs are properly formed
        assert amendment.changed_url.startswith("https://www.legislation.gov.uk/id/")
        assert amendment.affecting_url.startswith("https://www.legislation.gov.uk/id/")
