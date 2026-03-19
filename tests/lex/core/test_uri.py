"""Tests for canonical URI normalisation."""

import importlib.util
from pathlib import Path

# Load uri.py directly to avoid lex.core.__init__ triggering Qdrant connection
_uri_path = Path(__file__).resolve().parents[3] / "src" / "lex" / "core" / "uri.py"
_spec = importlib.util.spec_from_file_location("lex.core.uri", _uri_path)
_uri = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_uri)

normalise_legislation_uri = _uri.normalise_legislation_uri
CANONICAL_BASE = _uri.CANONICAL_BASE


class TestNormaliseLegislationUri:
    """Test all URI variant handling."""

    def test_short_form_to_full_url(self):
        result = normalise_legislation_uri("ukpga/2023/52")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_https_to_http(self):
        result = normalise_legislation_uri("https://www.legislation.gov.uk/id/ukpga/2023/52")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_missing_id_segment(self):
        """dc:identifier format missing /id/ segment."""
        result = normalise_legislation_uri("http://www.legislation.gov.uk/ukpga/2023/52")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_enacted_suffix_stripped(self):
        result = normalise_legislation_uri("http://www.legislation.gov.uk/ukpga/2023/52/enacted")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_made_suffix_stripped(self):
        result = normalise_legislation_uri("http://www.legislation.gov.uk/id/uksi/2023/100/made")
        assert result == "http://www.legislation.gov.uk/id/uksi/2023/100"

    def test_created_suffix_stripped(self):
        result = normalise_legislation_uri("http://www.legislation.gov.uk/id/wsi/2023/50/created")
        assert result == "http://www.legislation.gov.uk/id/wsi/2023/50"

    def test_enacted_with_trailing_path(self):
        """dc:identifier like http://.../ukpga/2023/52/enacted/data.xml"""
        result = normalise_legislation_uri(
            "http://www.legislation.gov.uk/ukpga/2023/52/enacted/data.xml"
        )
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_https_missing_id_and_enacted(self):
        """Combined: https + missing /id/ + /enacted suffix."""
        result = normalise_legislation_uri("https://www.legislation.gov.uk/ukpga/2023/52/enacted")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_already_canonical_unchanged(self):
        canonical = "http://www.legislation.gov.uk/id/ukpga/2023/52"
        assert normalise_legislation_uri(canonical) == canonical

    def test_empty_string_returns_empty(self):
        assert normalise_legislation_uri("") == ""

    def test_none_returns_none(self):
        assert normalise_legislation_uri(None) is None

    def test_whitespace_stripped(self):
        result = normalise_legislation_uri("  ukpga/2023/52  ")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_regnal_year_identifier(self):
        """Historical legislation with regnal year identifiers."""
        result = normalise_legislation_uri("aep/Edw7/6/19")
        assert result == "http://www.legislation.gov.uk/id/aep/Edw7/6/19"

    def test_section_uri_normalised(self):
        """Section URIs derived from parent should also normalise."""
        result = normalise_legislation_uri(
            "http://www.legislation.gov.uk/ukpga/2023/52/enacted/section/1"
        )
        # /enacted gets stripped along with everything after it
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_leading_slash_short_form(self):
        """Short form with leading slash should not produce double slash."""
        result = normalise_legislation_uri("/ukpga/2023/52")
        assert result == "http://www.legislation.gov.uk/id/ukpga/2023/52"

    def test_canonical_base_constant(self):
        assert CANONICAL_BASE == "http://www.legislation.gov.uk/id/"
