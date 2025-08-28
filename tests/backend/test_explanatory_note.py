"""Integration tests for explanatory note API endpoints."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from lex.explanatory_note.models import (
    ExplanatoryNote,
    ExplanatoryNoteType,
)
from src.backend.main import app


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def test_search_explanatory_note_endpoint(client):
    """Test that the /explanatory_note/section/search endpoint returns valid data."""
    # Simple search with a query that should return results in most environments
    search_query = "purpose of legislation"

    response = client.get(
        "/explanatory_note/section/search",
        params={"query": search_query, "size": 5},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of explanatory notes"

    # If no notes found, test passes but with a warning
    if not data:
        pytest.skip(f"No explanatory notes found for query '{search_query}', skipping validation")

    # Validate each note against the model
    for note_data in data:
        try:
            note = ExplanatoryNote(**note_data)

            # Verify the note has the expected fields
            assert note.id, "id should not be empty"
            assert note.legislation_id, "legislation_id should not be empty"
            assert isinstance(note.route, list), "route should be a list"
            assert note.order >= 0, "order should be non-negative"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_explanatory_note_with_filters_endpoint(client):
    """Test that the /explanatory_note/section/search endpoint works with note_type and section_type filters."""
    # Search for notes with specific types
    search_query = "generic legislation"

    response = client.get(
        "/explanatory_note/section/search",
        params={
            "query": search_query,
            "note_type": ExplanatoryNoteType.OVERVIEW.value,
            "size": 5,
        },
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of explanatory notes"

    # If no notes found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No explanatory notes found for query '{search_query}' with filters, skipping validation"
        )

    # Validate each note against the model
    for note_data in data:
        try:
            note = ExplanatoryNote(**note_data)

            # Verify the note has the expected fields
            assert note.id, "id should not be empty"
            assert note.legislation_id, "legislation_id should not be empty"

            # Check if note_type matches the requested type
            if note.note_type:
                assert note.note_type == ExplanatoryNoteType.OVERVIEW, (
                    "note_type should match requested filter"
                )

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_get_explanatory_note_by_legislation_endpoint(client):
    """Test that the /explanatory_note/legislation/lookup endpoint returns valid data."""
    # Use a common legislation ID format that should exist in most environments
    test_legislation_id = "https://www.legislation.gov.uk/ukpga/2022/4"

    response = client.get(
        "/explanatory_note/legislation/lookup",
        params={"legislation_id": test_legislation_id, "limit": 10},
    )

    # Check response status
    # This endpoint could return 404 if legislation not found, which is valid
    if response.status_code == 404:
        pytest.skip(
            f"No explanatory notes found for legislation ID {test_legislation_id}, this is valid"
        )
        return

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of explanatory notes"

    # Validate each note against the model
    for note_data in data:
        try:
            note = ExplanatoryNote(**note_data)

            # Verify the note has the expected fields
            assert note.id, "id should not be empty"
            assert note.legislation_id == test_legislation_id, (
                "legislation_id should match the requested ID"
            )
            assert isinstance(note.route, list), "route should be a list"
            assert note.order >= 0, "order should be non-negative"

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_get_explanatory_note_by_section_endpoint(client):
    """Test that the /explanatory_note/section/lookup endpoint returns valid data."""
    # Use a common legislation ID and section number that might exist in most environments
    test_legislation_id = "https://www.legislation.gov.uk/ukpga/2022/4"
    test_section_number = 1

    response = client.get(
        "/explanatory_note/section/lookup",
        params={"legislation_id": test_legislation_id, "section_number": test_section_number},
    )

    # Check response status
    # This endpoint could return 404 if section not found, which is valid
    if response.status_code == 404:
        pytest.skip(
            f"No explanatory note found for legislation ID {test_legislation_id} and section {test_section_number}, this is valid"
        )
        return

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, dict), "Expected a single explanatory note object"

    # Validate the note against the model
    try:
        note = ExplanatoryNote(**data)

        # Verify the note has the expected fields
        assert note.id, "id should not be empty"
        assert note.legislation_id == test_legislation_id, (
            "legislation_id should match the requested ID"
        )
        assert note.section_number == test_section_number, (
            "section_number should match the requested section"
        )
        assert isinstance(note.route, list), "route should be a list"
        assert note.order >= 0, "order should be non-negative"

    except ValidationError as e:
        pytest.fail(f"Validation error: {e}")
