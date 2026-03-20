"""Unit tests for regnal year parsing in legislation models."""

import pytest

from lex.legislation.models import _parse_year_from_legislation_id


@pytest.mark.parametrize(
    "legislation_id, expected_year",
    [
        # Modern URIs — standard numeric year
        ("http://www.legislation.gov.uk/id/ukpga/2018/12", 2018),
        ("http://www.legislation.gov.uk/id/uksi/2024/523", 2024),
        ("http://www.legislation.gov.uk/id/asp/2010/13", 2010),
        # Victorian era (1837-1901)
        ("http://www.legislation.gov.uk/id/ukla/Vict/44-45/12", 1881),  # 1837 + 44
        ("http://www.legislation.gov.uk/id/ukla/Vict/63-64/198", 1900),  # 1837 + 63
        # Edwardian era (1901-1910)
        ("http://www.legislation.gov.uk/id/ukla/Edw7/3/198", 1904),  # 1901 + 3
        ("http://www.legislation.gov.uk/id/ukla/Edw7/4/142", 1905),  # 1901 + 4
        # George V (1910-1936)
        ("http://www.legislation.gov.uk/id/ukpga/Geo5/14-15/42", 1924),  # 1910 + 14
        # George III (1760-1820)
        ("http://www.legislation.gov.uk/id/ukpga/Geo3/41/90", 1801),  # 1760 + 41
        # George VI (1936-1952)
        ("http://www.legislation.gov.uk/id/ukpga/Geo6/10-11/44", 1946),  # 1936 + 10
        # Without session number — falls back to reign start
        ("http://www.legislation.gov.uk/id/ukla/Vict", 1837),
        # Edge cases
        ("", None),
        ("http://www.legislation.gov.uk/id/ukpga", None),  # Too few parts
        ("http://www.legislation.gov.uk/id/ukpga/unknown/12", None),  # Unparseable
    ],
)
def test_parse_year_from_legislation_id(legislation_id, expected_year):
    assert _parse_year_from_legislation_id(legislation_id) == expected_year
