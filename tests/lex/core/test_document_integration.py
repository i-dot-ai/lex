from datetime import datetime

import pytest
from pydantic import BaseModel

from lex.core.clients import get_elasticsearch_client
from lex.core.document import (
    documents_to_batches,
    generate_documents,
    update_documents,
    upload_documents,
)


# Test models for integration testing
class LegislationDocument(BaseModel):
    id: str
    title: str
    content: str
    year: int
    legislation_type: str
    created_at: datetime = datetime.now()


class CaselawDocument(BaseModel):
    id: str
    case_name: str
    court: str
    judgment_date: datetime
    summary: str


class TestDocumentIntegration:
    """Integration tests for document functions with real Elasticsearch."""

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_full_document_pipeline_legislation(self):
        """Test complete document pipeline with legislation documents."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = "test-lex-legislation-integration"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Create index with appropriate mapping
            mappings = {
                "properties": {
                    "title": {"type": "text", "analyzer": "english"},
                    "content": {"type": "text", "analyzer": "english"},
                    "year": {"type": "integer"},
                    "legislation_type": {"type": "keyword"},
                    "created_at": {"type": "date"},
                }
            }

            es_client.indices.create(index=test_index, body={"mappings": mappings})

            # Prepare test data
            source_data = [
                {
                    "id": "ukpga-2024-1",
                    "title": "Data Protection Act 2024",
                    "content": "An Act to make provision about the processing of personal data and for connected purposes.",
                    "year": 2024,
                    "legislation_type": "ukpga",
                },
                {
                    "id": "ukpga-2024-2",
                    "title": "Digital Services Act 2024",
                    "content": "An Act to regulate digital services and online platforms.",
                    "year": 2024,
                    "legislation_type": "ukpga",
                },
                {
                    "id": "uksi-2024-100",
                    "title": "Data Protection Regulations 2024",
                    "content": "Regulations implementing the Data Protection Act 2024.",
                    "year": 2024,
                    "legislation_type": "uksi",
                },
            ]

            # Test document generation
            documents = list(generate_documents(source_data, LegislationDocument))
            assert len(documents) == 3
            assert all(isinstance(doc, LegislationDocument) for doc in documents)

            # Test document upload
            upload_documents(test_index, documents, batch_size=2, es_client=es_client)

            # Wait for indexing
            es_client.indices.refresh(index=test_index)

            # Verify documents were uploaded
            search_result = es_client.search(index=test_index, body={"query": {"match_all": {}}})
            assert search_result["hits"]["total"]["value"] == 3

            # Test search functionality
            search_result = es_client.search(
                index=test_index, body={"query": {"match": {"title": "Data Protection"}}}
            )

            # Should find both Data Protection Act and Regulations
            assert search_result["hits"]["total"]["value"] == 2

            # Test filtering by legislation type
            search_result = es_client.search(
                index=test_index, body={"query": {"term": {"legislation_type": "ukpga"}}}
            )

            assert search_result["hits"]["total"]["value"] == 2

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_document_update_operations(self):
        """Test document update operations with real Elasticsearch."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = "test-lex-update-integration"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Create index
            mappings = {
                "properties": {
                    "case_name": {"type": "text"},
                    "court": {"type": "keyword"},
                    "judgment_date": {"type": "date"},
                    "summary": {"type": "text"},
                }
            }

            es_client.indices.create(index=test_index, body={"mappings": mappings})

            # Initial documents
            initial_docs = [
                CaselawDocument(
                    id="case-1",
                    case_name="Smith v Jones",
                    court="High Court",
                    judgment_date=datetime(2024, 1, 15),
                    summary="Initial summary of the case",
                ),
                CaselawDocument(
                    id="case-2",
                    case_name="Brown v Wilson",
                    court="Court of Appeal",
                    judgment_date=datetime(2024, 2, 20),
                    summary="Another case summary",
                ),
            ]

            # Upload initial documents
            upload_documents(test_index, initial_docs, es_client=es_client)
            es_client.indices.refresh(index=test_index)

            # Verify initial upload
            search_result = es_client.search(index=test_index, body={"query": {"match_all": {}}})
            assert search_result["hits"]["total"]["value"] == 2

            # Test document updates
            updated_docs = [
                CaselawDocument(
                    id="case-1",
                    case_name="Smith v Jones",
                    court="High Court",
                    judgment_date=datetime(2024, 1, 15),
                    summary="Updated summary with more detailed analysis of the judgment",
                ),
                # Add a new document
                CaselawDocument(
                    id="case-3",
                    case_name="Taylor v Davis",
                    court="Supreme Court",
                    judgment_date=datetime(2024, 3, 10),
                    summary="New case added via update operation",
                ),
            ]

            # Perform updates
            update_documents(test_index, updated_docs, es_client=es_client)
            es_client.indices.refresh(index=test_index)

            # Verify updates
            search_result = es_client.search(index=test_index, body={"query": {"match_all": {}}})
            assert search_result["hits"]["total"]["value"] == 3

            # Check that case-1 was updated
            case_1_result = es_client.get(index=test_index, id="case-1")
            assert "more detailed analysis" in case_1_result["_source"]["summary"]

            # Check that case-3 was added
            case_3_result = es_client.get(index=test_index, id="case-3")
            assert case_3_result["_source"]["case_name"] == "Taylor v Davis"
            assert case_3_result["_source"]["court"] == "Supreme Court"

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_large_batch_processing(self):
        """Test processing large batches of documents."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = "test-lex-large-batch-integration"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Create index
            mappings = {
                "properties": {
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "year": {"type": "integer"},
                    "legislation_type": {"type": "keyword"},
                }
            }

            es_client.indices.create(index=test_index, body={"mappings": mappings})

            # Generate a large number of documents
            large_dataset = []
            for i in range(250):  # Large enough to test batching
                doc_data = {
                    "id": f"doc-{i:04d}",
                    "title": f"Test Legislation {i}",
                    "content": f"This is the content for test legislation number {i}. It contains various provisions and clauses.",
                    "year": 2020 + (i % 5),  # Years 2020-2024
                    "legislation_type": "ukpga" if i % 2 == 0 else "uksi",
                }
                large_dataset.append(doc_data)

            # Test document generation with large dataset
            documents = list(generate_documents(large_dataset, LegislationDocument))
            assert len(documents) == 250

            # Test batching
            batches = list(documents_to_batches(documents, batch_size=20))
            assert len(batches) == 13  # 250 / 20 = 12.5, so 13 batches
            assert len(batches[-1]) == 10  # Last batch should have 10 items

            # Test upload with custom batch size
            upload_documents(test_index, documents, batch_size=25, es_client=es_client)
            es_client.indices.refresh(index=test_index)

            # Verify all documents were uploaded
            search_result = es_client.search(
                index=test_index,
                body={
                    "query": {"match_all": {}},
                    "size": 0,  # Just get count
                },
            )
            assert search_result["hits"]["total"]["value"] == 250

            # Test aggregations on the large dataset
            agg_result = es_client.search(
                index=test_index,
                body={
                    "size": 0,
                    "aggs": {
                        "by_year": {"terms": {"field": "year"}},
                        "by_type": {"terms": {"field": "legislation_type"}},
                    },
                },
            )

            # Verify aggregations
            year_buckets = agg_result["aggregations"]["by_year"]["buckets"]
            assert len(year_buckets) == 5  # Years 2020-2024

            type_buckets = agg_result["aggregations"]["by_type"]["buckets"]
            assert len(type_buckets) == 2  # ukpga and uksi

            # Verify roughly equal distribution
            ukpga_count = next(b["doc_count"] for b in type_buckets if b["key"] == "ukpga")
            uksi_count = next(b["doc_count"] for b in type_buckets if b["key"] == "uksi")
            assert abs(ukpga_count - uksi_count) <= 1  # Should be 125 each

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)

    def test_document_generation_edge_cases(self):
        """Test document generation with various edge cases."""

        # Test with mixed valid and invalid data
        mixed_data = [
            {
                "id": "valid-1",
                "title": "Valid Doc",
                "content": "Content",
                "year": 2024,
                "legislation_type": "ukpga",
            },
            {
                "id": "invalid-1",
                "title": "Missing content",
                "year": 2024,
                "legislation_type": "ukpga",
            },  # Missing content
            {
                "id": "valid-2",
                "title": "Another Valid",
                "content": "More content",
                "year": 2023,
                "legislation_type": "uksi",
            },
            None,  # None value
            {
                "id": "invalid-2",
                "content": "Missing title",
                "year": 2024,
                "legislation_type": "ukpga",
            },  # Missing title
        ]

        # Should skip invalid documents and None values
        documents = list(generate_documents(mixed_data, LegislationDocument))
        assert len(documents) == 2
        assert documents[0].id == "valid-1"
        assert documents[1].id == "valid-2"

        # Test with empty dataset
        empty_documents = list(generate_documents([], LegislationDocument))
        assert len(empty_documents) == 0

        # Test with all invalid data
        invalid_data = [
            {"id": "invalid-1"},  # Missing required fields
            {"title": "No ID"},  # Missing ID
            None,
        ]

        invalid_documents = list(generate_documents(invalid_data, LegislationDocument))
        assert len(invalid_documents) == 0

    def test_batching_edge_cases(self):
        """Test document batching with edge cases."""

        # Test with empty list
        empty_batches = list(documents_to_batches([], batch_size=10))
        assert len(empty_batches) == 0

        # Test with single item
        single_item = [{"id": "1"}]
        single_batches = list(documents_to_batches(single_item, batch_size=10))
        assert len(single_batches) == 1
        assert len(single_batches[0]) == 1

        # Test with batch size of 1
        items = [1, 2, 3, 4, 5]
        unit_batches = list(documents_to_batches(items, batch_size=1))
        assert len(unit_batches) == 5
        assert all(len(batch) == 1 for batch in unit_batches)

        # Test with large batch size
        small_list = [1, 2, 3]
        large_batch = list(documents_to_batches(small_list, batch_size=100))
        assert len(large_batch) == 1
        assert len(large_batch[0]) == 3


class TestDocumentRealWorldScenarios:
    """Test document functions with real-world-like scenarios."""

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_legislation_search_scenario(self):
        """Test a realistic legislation search scenario."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = "test-lex-search-scenario"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Create index with search-optimized mapping
            mappings = {
                "properties": {
                    "title": {
                        "type": "text",
                        "analyzer": "english",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "content": {"type": "text", "analyzer": "english"},
                    "year": {"type": "integer"},
                    "legislation_type": {"type": "keyword"},
                }
            }

            es_client.indices.create(index=test_index, body={"mappings": mappings})

            # Realistic legislation data
            legislation_data = [
                {
                    "id": "ukpga-2018-12",
                    "title": "Data Protection Act 2018",
                    "content": "An Act to make provision for the regulation of the processing of information relating to individuals; to make provision in connection with the Information Commissioner's regulatory functions in relation to the processing of information; to make provision for a direct marketing code of practice; and for connected purposes.",
                    "year": 2018,
                    "legislation_type": "ukpga",
                },
                {
                    "id": "ukpga-2023-50",
                    "title": "Online Safety Act 2023",
                    "content": "An Act to make provision about the regulation of internet services; to make provision about the powers and duties of OFCOM in relation to internet services; to make provision about duties of care owed by providers of regulated services; and for connected purposes.",
                    "year": 2023,
                    "legislation_type": "ukpga",
                },
                {
                    "id": "uksi-2019-419",
                    "title": "The Data Protection, Privacy and Electronic Communications (Amendments etc) (EU Exit) Regulations 2019",
                    "content": "These Regulations are made in exercise of the powers conferred by section 8(1) of, and paragraph 21 of Schedule 7 to, the European Union (Withdrawal) Act 2018 in order to address failures of retained EU law to operate effectively and other deficiencies arising from the withdrawal of the United Kingdom from the European Union.",
                    "year": 2019,
                    "legislation_type": "uksi",
                },
                {
                    "id": "ukpga-2000-36",
                    "title": "Freedom of Information Act 2000",
                    "content": "An Act to make provision for the disclosure of information held by public authorities or by persons providing services for them and to amend the Data Protection Act 1998 and the Public Records Act 1958; and for connected purposes.",
                    "year": 2000,
                    "legislation_type": "ukpga",
                },
            ]

            # Upload documents
            documents = list(generate_documents(legislation_data, LegislationDocument))
            upload_documents(test_index, documents, es_client=es_client)
            es_client.indices.refresh(index=test_index)

            # Test various search scenarios

            # 1. Search for data protection legislation
            data_protection_search = es_client.search(
                index=test_index,
                body={
                    "query": {
                        "multi_match": {
                            "query": "data protection",
                            "fields": ["title^2", "content"],
                        }
                    }
                },
            )

            assert data_protection_search["hits"]["total"]["value"] >= 2

            # 2. Filter by legislation type and year range
            recent_acts_search = es_client.search(
                index=test_index,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"legislation_type": "ukpga"}},
                                {"range": {"year": {"gte": 2018}}},
                            ]
                        }
                    }
                },
            )

            assert recent_acts_search["hits"]["total"]["value"] == 2  # 2018 and 2023 Acts

            # 3. Complex search with multiple conditions
            complex_search = es_client.search(
                index=test_index,
                body={
                    "query": {
                        "bool": {
                            "must": [{"match": {"content": "regulation"}}],
                            "filter": [{"range": {"year": {"gte": 2000}}}],
                        }
                    },
                    "sort": [{"year": {"order": "desc"}}],
                },
            )

            # Should find multiple documents, sorted by year descending
            assert complex_search["hits"]["total"]["value"] >= 2
            hits = complex_search["hits"]["hits"]
            years = [hit["_source"]["year"] for hit in hits]
            assert years == sorted(years, reverse=True)

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)


# Fixtures
@pytest.fixture(scope="session")
def elasticsearch_client():
    """Session-scoped fixture for Elasticsearch client."""
    client = get_elasticsearch_client()
    if client:
        yield client
    else:
        pytest.skip("Elasticsearch not available for integration tests")


@pytest.fixture
def sample_legislation_data():
    """Fixture providing sample legislation data."""
    return [
        {
            "id": "ukpga-2024-1",
            "title": "Test Act 2024",
            "content": "An Act to test various provisions.",
            "year": 2024,
            "legislation_type": "ukpga",
        },
        {
            "id": "uksi-2024-100",
            "title": "Test Regulations 2024",
            "content": "Regulations to implement the Test Act.",
            "year": 2024,
            "legislation_type": "uksi",
        },
    ]
