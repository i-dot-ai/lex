"""Integration tests for explanatory note package."""

from lex.explanatory_note.scraper import ExplanatoryNoteScraperAndParser
from lex.legislation.models import LegislationType


def test_explanatory_note_integration():
    """Test the full explanatory note scraping and parsing pipeline."""
    # Initialize components
    scraper_and_parser = ExplanatoryNoteScraperAndParser()

    # Scrape and parse content
    explanatory_note = []
    for url, explanatory_note_soup in scraper_and_parser.scrape_and_parse_content(
        years=[2024], types=[LegislationType.UKPGA], limit=10
    ):
        explanatory_note.append(explanatory_note_soup)

    # Assertions
    assert len(explanatory_note) > 0, "Should have parsed at least one explanatory note"

    # Check that each explanatory note has basic required attributes
    for note in explanatory_note:
        assert note is not None
        # Add more specific assertions based on the ExplanatoryNote model structure
        # These would need to be updated based on the actual model implementation
        assert hasattr(note, "id")  # Assuming there's a content field
        assert hasattr(note, "legislation_id")  # Assuming there's a reference to the legislation
