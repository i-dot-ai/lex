"""Integration tests for caselaw API endpoints."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from lex.caselaw.models import Caselaw, CaselawSection, Court, CourtDivision
from src.backend.main import app


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def test_search_caselaw_endpoint(client):
    """Test that the /caselaw/search endpoint returns valid data."""
    # Simple search with a query that should return results in most environments
    search_query = "innocent or guilty"

    response = client.post(
        "/caselaw/search",
        json={"query": search_query, "is_semantic_search": True, "size": 5},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of caselaw"

    # If no caselaw found, test passes but with a warning
    if not data:
        pytest.skip(f"No caselaw found for query '{search_query}', skipping validation")

    # Validate each caselaw against the model
    for caselaw_data in data:
        try:
            caselaw = Caselaw(**caselaw_data)

            # Verify the caselaw has the expected fields
            assert caselaw.id, "id should not be empty"
            assert caselaw.court, "court should not be empty"
            assert caselaw.year, "year should not be empty"
            assert caselaw.number, "number should not be empty"
            assert caselaw.name, "name should not be empty"
            assert caselaw.cite_as, "cite_as should not be empty"
            assert caselaw.date, "date should not be empty"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_caselaw_with_filters_endpoint(client):
    """Test that the /caselaw/search endpoint works with filters."""
    # Search for Supreme Court cases from 2020-2023
    response = client.post(
        "/caselaw/search",
        json={"court": [Court.UKSC.value], "year_from": 2020, "year_to": 2025, "size": 5},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of caselaw"

    # If no caselaw found, test passes but with a warning
    if not data:
        pytest.skip("No Supreme Court cases found for 2020-2023, skipping validation")

    # Validate each caselaw against the model
    for caselaw_data in data:
        try:
            caselaw = Caselaw(**caselaw_data)

            # Verify the caselaw has the expected fields
            assert caselaw.id, "id should not be empty"
            assert caselaw.court == Court.UKSC, "court should be UKSC"
            assert 2020 <= caselaw.year <= 2025, "year should be between 2020 and 2025"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_caselaw_section_endpoint(client):
    """Test that the /caselaw/section/search endpoint returns valid data."""
    # Simple search with a query that should return results in most environments
    search_query = "innocent or guilty"

    response = client.post(
        "/caselaw/section/search",
        json={"query": search_query, "limit": 5},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of caselaw sections"

    # If no caselaw sections found, test passes but with a warning
    if not data:
        pytest.skip(f"No caselaw sections found for query '{search_query}', skipping validation")

    # Validate each caselaw section against the model
    for section_data in data:
        try:
            section = CaselawSection(**section_data)

            # Verify the section has the expected fields
            assert section.id, "id should not be empty"
            assert section.caselaw_id, "caselaw_id should not be empty"
            assert section.court, "court should not be empty"
            assert section.year, "year should not be empty"
            assert section.number, "number should not be empty"
            assert section.cite_as, "cite_as should not be empty"
            assert isinstance(section.route, list), "route should be a list"
            assert section.order >= 0, "order should be non-negative"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_caselaw_section_with_filters_endpoint(client):
    """Test that the /caselaw/section/search endpoint works with filters."""
    # Search for Court of Appeal (Civil Division) cases from 2020-2023
    response = client.post(
        "/caselaw/section/search",
        json={
            "court": [Court.EWCA.value],
            "division": [CourtDivision.CIV.value],
            "year_from": 2020,
            "year_to": 2025,
            "limit": 5,
        },
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of caselaw sections"

    # If no caselaw sections found, test passes but with a warning
    if not data:
        pytest.skip("No Court of Appeal (Civil) sections found for 2020-2023, skipping validation")

    # Validate each caselaw section against the model
    for section_data in data:
        try:
            section = CaselawSection(**section_data)

            # Verify the section has the expected fields
            assert section.id, "id should not be empty"
            assert section.court == Court.EWCA, "court should be EWCA"
            assert section.division == CourtDivision.CIV, "division should be CIV"
            assert 2020 <= section.year <= 2025, "year should be between 2020 and 2025"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")
