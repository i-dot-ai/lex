"""Integration tests for legislation API endpoints."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from lex.legislation.models import Legislation, LegislationSection, LegislationType
from src.backend.main import app


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def test_search_legislation_sections_endpoint(client):
    """Test that the /legislation/section/search endpoint returns valid data."""
    # Simple search with a query that should return results in most environments
    search_query = "environmental protection"

    response = client.post(
        "/legislation/section/search",
        json={"query": search_query, "size": 5},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of legislation sections"

    # If no legislation sections found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No legislation sections found for query '{search_query}', skipping validation"
        )

    # Validate each legislation section against the model
    for section_data in data:
        try:
            section = LegislationSection(**section_data)

            # Verify the section has the expected fields
            assert section.id, "id should not be empty"
            assert section.uri, "uri should not be empty"
            assert section.title, "title should not be empty"
            assert section.legislation_title, "legislation_title should not be empty"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_legislation_sections_with_filters_endpoint(client):
    """Test that the /legislation/section/search endpoint works with filters."""
    # Search for primary legislation sections from 2020-2023
    search_query = "covid"

    response = client.post(
        "/legislation/section/search",
        json={
            "query": search_query,
            "legislation_type": [LegislationType.UKPGA.value],
            "year_from": 2020,
            "year_to": 2023,
            "size": 5,
        },
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of legislation sections"

    # If no legislation sections found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No legislation sections found for query '{search_query}' with filters, skipping validation"
        )

    # Validate each legislation section against the model
    for section_data in data:
        try:
            section = LegislationSection(**section_data)

            # Verify the section has the expected fields and filter conditions
            assert section.id, "id should not be empty"
            assert section.legislation_type == LegislationType.UKPGA, (
                "legislation_type should match filter"
            )
            assert 2020 <= section.legislation_year <= 2023, "year should be between 2020 and 2023"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_legislation_acts_endpoint(client):
    """Test that the /legislation/search endpoint returns valid data."""
    # Simple search with a query that should return results in most environments
    search_query = "finance"

    response = client.post(
        "/legislation/search",
        json={"query": search_query, "limit": 5},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of legislation acts"

    # If no legislation acts found, test passes but with a warning
    if not data:
        pytest.skip(f"No legislation acts found for query '{search_query}', skipping validation")

    # Validate each legislation act against the model
    for act_data in data:
        try:
            act = Legislation(**act_data)

            # Verify the act has the expected fields
            assert act.id, "id should not be empty"
            assert act.uri, "uri should not be empty"
            assert act.title, "title should not be empty"
            assert act.type, "type should not be empty"
            assert act.year, "year should not be empty"
            assert act.number, "number should not be empty"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_lookup_legislation_endpoint(client):
    """Test that the /legislation/lookup endpoint returns valid data."""
    # Use a legislation that should exist in most environments
    test_type = LegislationType.UKPGA
    test_year = 2022
    test_number = 45  # Usually the first act of a year exists

    response = client.post(
        "/legislation/lookup",
        json={"legislation_type": test_type.value, "year": test_year, "number": test_number},
    )

    # Check response status
    # This endpoint could return 404 if legislation not found, which is valid
    if response.status_code == 404:
        pytest.skip(
            f"Legislation not found: {test_type.value} {test_year} No. {test_number}, this is valid"
        )
        return

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, dict), "Expected a single legislation object"

    # Validate the legislation against the model
    try:
        legislation = Legislation(**data)

        # Verify the legislation has the expected fields
        assert legislation.id, "id should not be empty"
        assert legislation.uri, "uri should not be empty"
        assert legislation.title, "title should not be empty"
        assert legislation.type == test_type, "type should match requested type"
        assert legislation.year == test_year, "year should match requested year"
        assert legislation.number == test_number, "number should match requested number"

    except ValidationError as e:
        pytest.fail(f"Validation error: {e}")


def test_get_legislation_sections_endpoint(client):
    """Test that the /legislation/section/lookup endpoint returns valid data."""
    # Use a title that should exist in most environments
    test_title = "Finance Act 2022"

    response = client.post(
        "/legislation/section/lookup",
        json={"title": test_title, "limit": 10},
    )

    # Check response status
    # This endpoint could return 404 if title not found, which is valid
    if response.status_code == 404:
        pytest.skip(f"No sections found for legislation title: {test_title}, this is valid")
        return

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of legislation sections"

    # Validate each section against the model
    for section_data in data:
        try:
            section = LegislationSection(**section_data)

            # Verify the section has the expected fields
            assert section.id, "id should not be empty"
            assert section.uri, "uri should not be empty"
            assert section.legislation_title == test_title, (
                "legislation_title should match the requested title"
            )
            assert section.number, "number should not be empty"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")
