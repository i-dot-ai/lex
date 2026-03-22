"""Unit tests for regnal year parsing."""

import pytest

from lex.legislation.models import _parse_year_from_legislation_id
from lex.legislation.regnal import (
    compute_regnal_year,
    parse_legislation_year,
    resolve_monarch,
)

# ── Strategy 1-2: Standard and canonical regnal URIs ─────────────────────


@pytest.mark.parametrize(
    "legislation_id, expected_year",
    [
        # Modern URIs — standard numeric year
        ("http://www.legislation.gov.uk/id/ukpga/2018/12", 2018),
        ("http://www.legislation.gov.uk/id/uksi/2024/523", 2024),
        ("http://www.legislation.gov.uk/id/asp/2010/13", 2010),
        # Victorian era (1837-1901)
        ("http://www.legislation.gov.uk/id/ukla/Vict/44-45/12", 1881),
        ("http://www.legislation.gov.uk/id/ukla/Vict/63-64/198", 1900),
        # Edwardian era (1901-1910)
        ("http://www.legislation.gov.uk/id/ukla/Edw7/3/198", 1904),
        ("http://www.legislation.gov.uk/id/ukla/Edw7/4/142", 1905),
        # George V (1910-1936)
        ("http://www.legislation.gov.uk/id/ukpga/Geo5/14-15/42", 1924),
        # George III (1760-1820)
        ("http://www.legislation.gov.uk/id/ukpga/Geo3/41/90", 1801),
        # George VI (1936-1952)
        ("http://www.legislation.gov.uk/id/ukpga/Geo6/10-11/44", 1946),
        # Without session number — falls back to reign start
        ("http://www.legislation.gov.uk/id/ukla/Vict", 1837),
        # Edge cases
        ("", None),
        ("http://www.legislation.gov.uk/id/ukpga", None),
        ("http://www.legislation.gov.uk/id/ukpga/unknown/12", None),
    ],
)
def test_standard_and_canonical_uris(legislation_id, expected_year):
    assert parse_legislation_year(legislation_id) == expected_year


def test_backwards_compatible_import():
    """The old _parse_year_from_legislation_id still works via regnal.py."""
    assert _parse_year_from_legislation_id("http://www.legislation.gov.uk/id/ukpga/2018/12") == 2018
    assert (
        _parse_year_from_legislation_id("http://www.legislation.gov.uk/id/ukla/Vict/44-45/12")
        == 1881
    )


# ── Strategy 3: Explicit year in URI ─────────────────────────────────────


@pytest.mark.parametrize(
    "uri, expected_year",
    [
        ("52 & 53 Vict. c. clviii (1889)", 1889),
        ("S.I. 1948 No. 845", 1948),
        ("S.R. & O. 1948 No. 845", 1948),
    ],
)
def test_explicit_year(uri, expected_year):
    assert parse_legislation_year(uri) == expected_year


# ── Strategy 4: Regnal with nonstandard separators ───────────────────────


@pytest.mark.parametrize(
    "uri, expected_year",
    [
        # Freetext citations
        ("52 & 53 Vict. c. clviii", 1888),
        ("14 Geo. 6. c. xliii", 1949),
        # Concatenated session-monarch
        ("52-53Vict/cxcvii", 1888),
        # Underscore-separated (full URI path)
        ("http://www.legislation.gov.uk/id/ukla/Vict_44_45/c12", 1880),
    ],
)
def test_regnal_with_separators(uri, expected_year):
    assert parse_legislation_year(uri) == expected_year


# ── Strategy 5: Combined reign references ────────────────────────────────


@pytest.mark.parametrize(
    "uri, expected_year",
    [
        ("Edw8and1Geo6/1/100", 1936),
        ("10-Edw-7-&-1-Geo-5-ch-1", 1910),
    ],
)
def test_combined_reign(uri, expected_year):
    assert parse_legislation_year(uri) == expected_year


# ── Strategy 7: Number before monarch ────────────────────────────────────


@pytest.mark.parametrize(
    "uri, expected_year",
    [
        ("5-edw-7-c-138", 1905),
    ],
)
def test_number_before_monarch(uri, expected_year):
    assert parse_legislation_year(uri) == expected_year


# ── Strategy 8: Embedded year in Act names ───────────────────────────────


@pytest.mark.parametrize(
    "uri, expected_year",
    [
        ("[UNCLEAR: Liverpool_Sanitary_Amendment_Act_1854_Cap.xv]", 1854),
        ("local/Metropolitan_District_Railway_Act_1881_c.86", 1881),
    ],
)
def test_embedded_year(uri, expected_year):
    assert parse_legislation_year(uri) == expected_year


# ── Strategy 9: Broad year extraction ────────────────────────────────────


@pytest.mark.parametrize(
    "uri, expected_year",
    [
        ("1949 No. 2170", 1949),
    ],
)
def test_broad_year(uri, expected_year):
    assert parse_legislation_year(uri) == expected_year


# ── Strategy 10: Short title from text ───────────────────────────────────


@pytest.mark.parametrize(
    "legislation_id, text, expected_year",
    [
        # URI has no year signal — text extraction should kick in
        (
            "[UNCLEAR: reference not provided]",
            "This Act may be cited as the Elementary Education Act 1891",
            1891,
        ),
        (
            "[UNCLEAR: reference not provided]",
            "Short Title.\u2014The Court of Session Act, 1868",
            1868,
        ),
        # No text signal either — should return None
        (
            "[UNCLEAR: reference not provided]",
            "Some text with no year reference whatsoever",
            None,
        ),
    ],
)
def test_short_title_text(legislation_id, text, expected_year):
    assert parse_legislation_year(legislation_id, text=text) == expected_year


# ── resolve_monarch ──────────────────────────────────────────────────────


def test_resolve_monarch_canonical():
    result = resolve_monarch("Vict")
    assert result == ("Vict", 1837, 1901)


def test_resolve_monarch_alias():
    result = resolve_monarch("victoriae")
    assert result == ("Vict", 1837, 1901)


def test_resolve_monarch_ambiguous():
    """Ambiguous names (no number suffix) return None."""
    assert resolve_monarch("george") is None
    assert resolve_monarch("edward") is None


def test_resolve_monarch_with_number():
    result = resolve_monarch("Geo5")
    assert result == ("Geo5", 1910, 1936)


# ── compute_regnal_year ──────────────────────────────────────────────────


def test_compute_regnal_year_valid():
    # Victoria session 44: 1837 + 44 - 1 = 1880
    assert compute_regnal_year(1837, 1901, 44) == 1880


def test_compute_regnal_year_outside_reign():
    # Session 200 would be 1837 + 200 - 1 = 2036 — outside Victoria's reign
    assert compute_regnal_year(1837, 1901, 200) is None
