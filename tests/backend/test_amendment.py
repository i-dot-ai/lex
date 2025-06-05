"""Integration tests for amendment API endpoints."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from lex.amendment.models import Amendment
from src.backend.main import app

# These tests will skip unless you've uploaded amendments to Elasticsearch
# Please ensure that you've run this command: python src/lex/main.py -m amendment --limit 500 -y 2022


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def test_search_amendments_endpoint(client):
    """Test that the /amendment/search endpoint returns valid data."""
    # Use a sample legislation ID that exists if we load amendments from 2022
    test_legislation_id = "https://www.legislation.gov.uk/id/asc/2022/1"

    # Test with search_amended=True
    response = client.post(
        "/amendment/search",
        json={"legislation_id": test_legislation_id, "search_amended": True, "size": 10},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of amendments"

    # If no amendments found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No amendments found for legislation {test_legislation_id}, skipping validation"
        )

    # Validate each amendment against the model
    for amendment_data in data:
        try:
            amendment = Amendment(**amendment_data)

            # Verify the amendment has the expected fields
            assert amendment.changed_legislation, "changed_legislation should not be empty"
            assert amendment.changed_url, "changed_url should not be empty"
            assert amendment.affecting_url, "affecting_url should not be empty"
            assert amendment.id, "id should not be empty"

            # If search_amended=True, the changed_url should contain the legislation_id
            assert test_legislation_id in amendment.changed_url

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_amendments_made_by_endpoint(client):
    """Test that the /amendment/search endpoint returns valid data when searching for amendments made by."""
    # Use a sample legislation ID that exists if we load amendments from 2022
    test_legislation_id = "https://www.legislation.gov.uk/id/wsi/2022/1318"

    # Test with search_amended=False
    response = client.post(
        "/amendment/search",
        json={"legislation_id": test_legislation_id, "search_amended": False, "size": 10},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of amendments"

    # If no amendments found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No amendments found for legislation {test_legislation_id}, skipping validation"
        )

    # Validate each amendment against the model
    for amendment_data in data:
        try:
            amendment = Amendment(**amendment_data)

            # Verify the amendment has the expected fields
            assert amendment.changed_legislation, "changed_legislation should not be empty"
            assert amendment.changed_url, "changed_url should not be empty"
            assert amendment.affecting_url, "affecting_url should not be empty"
            assert amendment.id, "id should not be empty"

            # If search_amended=False, the affecting_url should contain the legislation_id
            assert test_legislation_id in amendment.affecting_url

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_amendment_sections_endpoint(client):
    """Test that the /amendment/section/search endpoint returns valid data."""
    # Use a sample provision ID that exists if we load amendments from 2022
    test_provision_id = "https://www.legislation.gov.uk/id/asc/2022/1/schedule/1"

    # Test with search_amended=True
    response = client.post(
        "/amendment/section/search",
        json={"provision_id": test_provision_id, "search_amended": True, "size": 10},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of amendments"

    # If no amendments found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No amendment sections found for provision {test_provision_id}, skipping validation"
        )

    # Validate each amendment against the model
    for amendment_data in data:
        try:
            amendment = Amendment(**amendment_data)

            # Verify the amendment has the expected fields
            assert amendment.changed_legislation, "changed_legislation should not be empty"
            assert amendment.changed_url, "changed_url should not be empty"
            assert amendment.affecting_url, "affecting_url should not be empty"
            assert amendment.id, "id should not be empty"
            assert amendment.changed_provision_url, "changed_provision_url should not be empty"

            # If search_amended=True, the changed_provision_url should contain the provision_id
            assert test_provision_id in amendment.changed_provision_url

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")


def test_search_amendment_sections_made_by_endpoint(client):
    """Test that the /amendment/section/search endpoint returns valid data when searching for amendments made by."""
    # Use a sample provision ID that exists if we load amendments from 2022
    test_provision_id = "https://www.legislation.gov.uk/id/wsi/2022/1318/article/2/c/viii"

    # Test with search_amended=False
    response = client.post(
        "/amendment/section/search",
        json={"provision_id": test_provision_id, "search_amended": False, "size": 10},
    )

    # Check response status
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Check response structure
    data = response.json()
    assert isinstance(data, list), "Expected a list of amendments"

    # If no amendments found, test passes but with a warning
    if not data:
        pytest.skip(
            f"No amendment sections found for provision {test_provision_id}, skipping validation"
        )

    # Validate each amendment against the model
    for amendment_data in data:
        try:
            amendment = Amendment(**amendment_data)

            # Verify the amendment has the expected fields
            assert amendment.changed_legislation, "changed_legislation should not be empty"
            assert amendment.changed_url, "changed_url should not be empty"
            assert amendment.affecting_url, "affecting_url should not be empty"
            assert amendment.id, "id should not be empty"
            assert amendment.affecting_provision_url, "affecting_provision_url should not be empty"

            # If search_amended=False, the affecting_provision_url should contain the provision_id
            assert test_provision_id in amendment.affecting_provision_url

        except ValidationError as e:
            pytest.fail(f"Validation error: {e}")
