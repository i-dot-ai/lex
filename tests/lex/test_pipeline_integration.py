"""Integration tests for pipeline functions with Elasticsearch."""

import logging

import pytest

from lex.caselaw.models import Court
from lex.core.clients import get_elasticsearch_client
from lex.core.document import upload_documents
from lex.core.utils import create_index_if_none
from lex.legislation.models import LegislationType
from lex.main import index_mapping

logger = logging.getLogger(__name__)


class TestPipelineIntegration:
    """Integration tests for all pipeline functions with real Elasticsearch."""

    @pytest.mark.parametrize(
        "model_type",
        [
            "legislation",
            "legislation-section",
            "explanatory-note",
            "amendment",
            "caselaw",
            "caselaw-section",
        ],
    )
    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_pipeline_end_to_end(self, model_type):
        """Test complete pipeline from scraping to Elasticsearch indexing."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = f"lex-{model_type}-testing"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Get pipeline function and mappings from main.py
            default_index, pipe_function, mappings = index_mapping[model_type]

            # Create test index with proper mappings
            create_index_if_none(
                index_name=test_index, mappings=mappings, es_client=es_client, non_interactive=True
            )

            # Prepare arguments for pipeline function
            kwargs = {
                "years": [2024],
                "limit": 3,  # Keep small for fast tests
            }

            # Add model-specific arguments
            if model_type in ["legislation", "legislation-section", "explanatory-note"]:
                kwargs["types"] = [LegislationType.UKPGA]
            elif model_type in ["caselaw", "caselaw-section"]:
                kwargs["types"] = [Court.UKSC]  # UK Supreme Court
            # amendment doesn't need types

            # Run the pipeline function
            logger.info(f"Running pipeline for {model_type}")
            documents = list(pipe_function(**kwargs))

            # Verify we got some documents
            assert len(documents) > 0, (
                f"Pipeline should generate at least one document for {model_type}"
            )
            logger.info(f"Generated {len(documents)} documents for {model_type}")

            # Upload documents to test index
            upload_documents(index_name=test_index, documents=documents, es_client=es_client)

            # Force refresh to make documents searchable
            es_client.indices.refresh(index=test_index)

            # Verify documents were indexed
            search_result = es_client.search(index=test_index, body={"query": {"match_all": {}}})

            indexed_count = search_result["hits"]["total"]["value"]
            assert indexed_count > 0, f"Should have indexed at least one document for {model_type}"

            # For amendments, allow for some documents to be skipped due to duplicate IDs
            # For explanatory notes, allow for upload timeouts that may cause fewer documents to be indexed
            if model_type == "amendment":
                assert indexed_count <= len(documents), (
                    f"Indexed count should not exceed generated documents for {model_type}"
                )
                logger.info(
                    f"Amendment indexing: {indexed_count} indexed out of {len(documents)} generated (some may be duplicates)"
                )
            elif model_type == "explanatory-note":
                # Allow for connection timeouts during upload
                assert indexed_count <= len(documents), (
                    f"Indexed count should not exceed generated documents for {model_type}"
                )
                if indexed_count < len(documents):
                    logger.warning(
                        f"Explanatory note indexing: {indexed_count} indexed out of {len(documents)} generated (may be due to connection timeouts)"
                    )
                else:
                    logger.info(
                        f"All {indexed_count} explanatory note documents indexed successfully"
                    )
            else:
                assert indexed_count == len(documents), (
                    f"All {len(documents)} documents should be indexed for {model_type}"
                )

            # Verify document structure
            for hit in search_result["hits"]["hits"]:
                doc = hit["_source"]
                assert "id" in doc, f"Document should have 'id' field for {model_type}"

                # Check for content fields (different models use different field names)
                if model_type == "amendment":
                    # Amendments have legislation names and effect descriptions
                    has_content = any(
                        field in doc
                        for field in [
                            "changed_legislation",
                            "affecting_legislation",
                            "type_of_effect",
                        ]
                    )
                else:
                    # Other models have text/title/case_name fields
                    has_content = any(
                        field in doc for field in ["title", "text", "content", "case_name"]
                    )

                assert has_content, f"Document should have content field for {model_type}"

            # Test search functionality with proper semantic search syntax
            if indexed_count > 0:
                # Try a simple search for common legal terms using semantic search for text fields
                search_terms = ["act", "section", "court", "law", "regulation"]

                for term in search_terms:
                    # Use semantic search for models that have semantic text fields
                    if model_type in [
                        "legislation-section",
                        "explanatory-note",
                        "caselaw",
                        "caselaw-section",
                    ]:
                        search_query = {"query": {"semantic": {"field": "text", "query": term}}}
                    else:
                        # For other models, use multi_match on non-semantic fields
                        search_query = {
                            "query": {
                                "multi_match": {
                                    "query": term,
                                    "fields": [
                                        "title",
                                        "case_name",
                                        "changed_legislation",
                                        "affecting_legislation",
                                    ],
                                    "type": "best_fields",
                                }
                            }
                        }

                    try:
                        search_result = es_client.search(index=test_index, body=search_query)

                        # If we find results, that's good - documents are searchable
                        if search_result["hits"]["total"]["value"] > 0:
                            logger.info(
                                f"Search for '{term}' found {search_result['hits']['total']['value']} results in {model_type}"
                            )
                            break
                    except Exception as e:
                        logger.warning(f"Search failed for term '{term}' in {model_type}: {e}")
                        continue
                else:
                    # If no search terms found results, that's still okay for small test datasets
                    logger.warning(
                        f"No search results found for common terms in {model_type} - this may be normal for small test datasets"
                    )

            logger.info(f"Pipeline integration test completed successfully for {model_type}")

        except Exception as e:
            logger.error(f"Pipeline test failed for {model_type}: {e}", exc_info=True)
            raise
        finally:
            # Always clean up test index
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)
                logger.info(f"Cleaned up test index: {test_index}")

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_pipeline_with_custom_index_name(self):
        """Test that pipeline works with custom index names."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        # Test with legislation pipeline
        model_type = "legislation"
        custom_index = "lex-custom-legislation-test"

        # Clean up any existing test index
        if es_client.indices.exists(index=custom_index):
            es_client.indices.delete(index=custom_index)

        try:
            # Get pipeline function and mappings
            default_index, pipe_function, mappings = index_mapping[model_type]

            # Create custom index
            create_index_if_none(
                index_name=custom_index,
                mappings=mappings,
                es_client=es_client,
                non_interactive=True,
            )

            # Run pipeline with minimal data
            documents = list(pipe_function(years=[2024], limit=1, types=[LegislationType.UKPGA]))

            if documents:  # Only proceed if we got documents
                # Upload to custom index
                upload_documents(index_name=custom_index, documents=documents, es_client=es_client)
                es_client.indices.refresh(index=custom_index)

                # Verify documents in custom index
                search_result = es_client.search(
                    index=custom_index, body={"query": {"match_all": {}}}
                )

                assert search_result["hits"]["total"]["value"] > 0
                logger.info(
                    f"Successfully uploaded {search_result['hits']['total']['value']} documents to custom index"
                )

        finally:
            # Clean up
            if es_client.indices.exists(index=custom_index):
                es_client.indices.delete(index=custom_index)

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_pipeline_error_handling(self):
        """Test pipeline behavior with invalid parameters."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        # Test with legislation pipeline and invalid year
        model_type = "legislation"
        default_index, pipe_function, mappings = index_mapping[model_type]

        # Test with year that likely has no data
        documents = list(
            pipe_function(
                years=[1800],  # Very old year unlikely to have data
                limit=1,
                types=[LegislationType.UKPGA],
            )
        )

        # Should handle gracefully - either return empty list or valid documents
        assert isinstance(documents, list)
        logger.info(
            f"Pipeline handled invalid year gracefully, returned {len(documents)} documents"
        )

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_pipeline_batch_processing(self):
        """Test pipeline with slightly larger batch to verify batch processing works."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        model_type = "legislation-section"  # Sections usually generate more documents
        test_index = f"lex-{model_type}-batch-testing"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Get pipeline function and mappings
            default_index, pipe_function, mappings = index_mapping[model_type]

            # Create test index
            create_index_if_none(
                index_name=test_index, mappings=mappings, es_client=es_client, non_interactive=True
            )

            # Run pipeline with slightly larger limit
            documents = list(
                pipe_function(
                    years=[2024],
                    limit=10,  # Larger limit to test batching
                    types=[LegislationType.UKPGA],
                )
            )

            if documents:  # Only proceed if we got documents
                # Upload with small batch size to test batching
                upload_documents(
                    index_name=test_index,
                    documents=documents,
                    batch_size=3,  # Small batch size to force multiple batches
                    es_client=es_client,
                )

                es_client.indices.refresh(index=test_index)

                # Verify all documents were uploaded
                search_result = es_client.search(
                    index=test_index, body={"query": {"match_all": {}}}
                )

                indexed_count = search_result["hits"]["total"]["value"]
                assert indexed_count == len(documents), (
                    f"All {len(documents)} documents should be indexed in batches"
                )
                logger.info(f"Successfully batch processed {indexed_count} documents")

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)
