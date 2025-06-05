import logging
import os
import tempfile

import pytest
from bs4 import BeautifulSoup

from lex.core.clients import get_elasticsearch_client
from lex.core.utils import (
    create_index_if_none,
    load_xml_file_to_soup,
    scroll_index,
    set_logging_level,
)


class TestUtilsIntegration:
    """Integration tests for utils functions with real services."""

    def test_set_logging_level_integration(self):
        """Test that logging level is actually set correctly."""
        # Test setting different log levels
        set_logging_level(logging.DEBUG)

        # Create a test logger and verify it has the correct level
        test_logger = logging.getLogger("lex.test_module")
        assert test_logger.getEffectiveLevel() == logging.DEBUG

        # Test changing to a different level
        set_logging_level(logging.WARNING)
        assert test_logger.getEffectiveLevel() == logging.WARNING

    def test_load_xml_file_integration(self):
        """Test XML file loading with real files."""
        # Create a temporary XML file
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<legislation>
    <title>Test Legislation Act 2024</title>
    <section id="1">
        <title>Definitions</title>
        <content>In this Act, unless the context otherwise requires...</content>
    </section>
    <section id="2">
        <title>Application</title>
        <content>This Act applies to all persons within the jurisdiction.</content>
    </section>
</legislation>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            # Test loading the XML file
            soup = load_xml_file_to_soup(temp_path)

            # Verify the structure
            assert isinstance(soup, BeautifulSoup)
            assert soup.find("title").text == "Test Legislation Act 2024"

            # Test finding sections
            sections = soup.find_all("section")
            assert len(sections) == 2
            assert sections[0]["id"] == "1"
            assert sections[1]["id"] == "2"

            # Test content extraction
            definitions_section = soup.find("section", {"id": "1"})
            assert "Definitions" in definitions_section.find("title").text
            assert (
                "unless the context otherwise requires" in definitions_section.find("content").text
            )

        finally:
            os.unlink(temp_path)

    def test_load_xml_file_with_complex_structure(self):
        """Test XML loading with more complex nested structure."""
        complex_xml = """<?xml version="1.0" encoding="UTF-8"?>
<legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation">
    <metadata>
        <title>Complex Act 2024</title>
        <year>2024</year>
        <number>42</number>
    </metadata>
    <body>
        <part id="part1">
            <title>Part 1 - General Provisions</title>
            <chapter id="ch1">
                <title>Chapter 1 - Definitions</title>
                <section id="s1">
                    <title>Interpretation</title>
                    <subsection id="s1-1">
                        <content>In this Act:</content>
                        <definition term="person">means an individual or corporation</definition>
                        <definition term="document">includes electronic records</definition>
                    </subsection>
                </section>
            </chapter>
        </part>
    </body>
</legislation>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(complex_xml)
            temp_path = f.name

        try:
            soup = load_xml_file_to_soup(temp_path)

            # Test namespace handling
            assert soup.find("legislation") is not None

            # Test nested structure navigation
            metadata = soup.find("metadata")
            assert metadata.find("title").text == "Complex Act 2024"
            assert metadata.find("year").text == "2024"

            # Test deep nesting
            definitions = soup.find_all("definition")
            assert len(definitions) == 2
            assert definitions[0]["term"] == "person"
            assert "individual or corporation" in definitions[0].text

        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_elasticsearch_index_operations_integration(self):
        """Test Elasticsearch index operations with real ES instance."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = "test-lex-utils-integration"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Test index creation
            mappings = {
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "content": {"type": "text"},
                        "created_at": {"type": "date"},
                    }
                }
            }

            create_index_if_none(test_index, mappings, es_client, non_interactive=True)

            # Verify index was created
            assert es_client.indices.exists(index=test_index)

            # Verify mapping was applied
            mapping = es_client.indices.get_mapping(index=test_index)
            properties = mapping[test_index]["mappings"]["properties"]
            assert "title" in properties
            assert properties["title"]["type"] == "text"

            # Test calling create_index_if_none again (should not error)
            create_index_if_none(test_index, mappings, es_client, non_interactive=True)

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)

    @pytest.mark.skipif(not get_elasticsearch_client(), reason="Elasticsearch not available")
    def test_scroll_index_integration(self):
        """Test scrolling through Elasticsearch index with real data."""
        es_client = get_elasticsearch_client()
        if not es_client:
            pytest.skip("Elasticsearch client not available")

        test_index = "test-lex-scroll-integration"

        # Clean up any existing test index
        if es_client.indices.exists(index=test_index):
            es_client.indices.delete(index=test_index)

        try:
            # Create index
            mappings = {
                "properties": {
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "doc_id": {"type": "keyword"},
                }
            }

            es_client.indices.create(index=test_index, body={"mappings": mappings})

            # Add test documents
            test_docs = [
                {
                    "doc_id": f"doc_{i}",
                    "title": f"Document {i}",
                    "content": f"Content for document {i}",
                }
                for i in range(25)  # Enough to test scrolling
            ]

            # Bulk index documents
            from elasticsearch import helpers

            actions = [
                {"_index": test_index, "_id": doc["doc_id"], "_source": doc} for doc in test_docs
            ]
            helpers.bulk(es_client, actions)

            # Wait for indexing to complete
            es_client.indices.refresh(index=test_index)

            # Test scrolling through all documents
            scrolled_docs = list(scroll_index(es_client, test_index, scroll_size=10))

            # Verify we got all documents
            assert len(scrolled_docs) == 25

            # Verify document structure
            for doc in scrolled_docs:
                assert "_id" in doc
                assert "_source" in doc
                assert "title" in doc["_source"]
                assert "content" in doc["_source"]

            # Test scrolling with specific fields
            scrolled_docs_fields = list(
                scroll_index(es_client, test_index, fields=["title", "doc_id"], scroll_size=5)
            )

            assert len(scrolled_docs_fields) == 25

            # Verify only requested fields are returned
            for doc in scrolled_docs_fields:
                source = doc["_source"]
                assert "title" in source
                assert "doc_id" in source
                # content should not be included
                assert "content" not in source

        finally:
            # Clean up
            if es_client.indices.exists(index=test_index):
                es_client.indices.delete(index=test_index)

    def test_xml_file_error_handling(self):
        """Test XML file loading error handling."""
        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            load_xml_file_to_soup("non_existent_file.xml")

        # Test with malformed XML (BeautifulSoup is forgiving, so this should still work)
        malformed_xml = "<root><unclosed_tag>content</root>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(malformed_xml)
            temp_path = f.name

        try:
            # Should still parse, but structure might be different
            soup = load_xml_file_to_soup(temp_path)
            assert isinstance(soup, BeautifulSoup)
            # BeautifulSoup will try to fix the structure
            assert soup.find("root") is not None

        finally:
            os.unlink(temp_path)

    def test_xml_with_different_encodings(self):
        """Test XML loading with different character encodings."""
        # Test with UTF-8 content including special characters
        utf8_xml = """<?xml version="1.0" encoding="UTF-8"?>
<legislation>
    <title>Loi sur les données personnelles</title>
    <section>
        <content>This section contains special characters: £, €, ñ, ü</content>
    </section>
</legislation>"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(utf8_xml)
            temp_path = f.name

        try:
            soup = load_xml_file_to_soup(temp_path)

            # Verify special characters are preserved
            title = soup.find("title").text
            assert "données" in title

            content = soup.find("content").text
            assert "£" in content
            assert "€" in content
            assert "ñ" in content
            assert "ü" in content

        finally:
            os.unlink(temp_path)


class TestUtilsRealWorldScenarios:
    """Test utils functions with real-world-like scenarios."""

    def test_legislation_xml_parsing(self):
        """Test parsing XML that resembles real UK legislation structure."""
        legislation_xml = """<?xml version="1.0" encoding="UTF-8"?>
<legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xsi:schemaLocation="http://www.legislation.gov.uk/namespaces/legislation">
    <ukm:Metadata xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata">
        <ukm:Number Value="42"/>
        <ukm:Year Value="2024"/>
        <ukm:ISBN Value="9780123456789"/>
    </ukm:Metadata>
    
    <prelims>
        <title>Data Protection Act 2024</title>
        <longtitle>
            <para>An Act to make provision about the processing of personal data.</para>
        </longtitle>
    </prelims>
    
    <body>
        <part id="part1">
            <title>Part 1 General</title>
            <chapter id="ch1">
                <title>Chapter 1 Preliminary</title>
                <section id="section1">
                    <title>Overview</title>
                    <subsection id="section1-1">
                        <para>This Act regulates the processing of personal data.</para>
                    </subsection>
                </section>
                <section id="section2">
                    <title>Definitions</title>
                    <subsection id="section2-1">
                        <para>In this Act—</para>
                        <definition id="def-personal-data">
                            <term>"personal data"</term>
                            <para>means any information relating to an identified or identifiable natural person;</para>
                        </definition>
                        <definition id="def-processing">
                            <term>"processing"</term>
                            <para>means any operation performed on personal data.</para>
                        </definition>
                    </subsection>
                </section>
            </chapter>
        </part>
    </body>
</legislation>"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(legislation_xml)
            temp_path = f.name

        try:
            soup = load_xml_file_to_soup(temp_path)

            # Test metadata extraction
            metadata = soup.find("metadata") or soup.find_all(attrs={"xmlns:ukm": True})
            assert soup.find(attrs={"Value": "42"}) or soup.find("ukm:Number")

            # Test title extraction
            title = soup.find("title")
            assert "Data Protection Act 2024" in title.text

            # Test structural navigation
            sections = soup.find_all("section")
            assert len(sections) >= 2

            # Test definition extraction
            definitions = soup.find_all("definition")
            assert len(definitions) == 2

            # Verify specific definitions
            personal_data_def = soup.find("definition", {"id": "def-personal-data"})
            assert personal_data_def is not None
            assert "personal data" in personal_data_def.find("term").text

            processing_def = soup.find("definition", {"id": "def-processing"})
            assert processing_def is not None
            assert "processing" in processing_def.find("term").text

        finally:
            os.unlink(temp_path)

    def test_large_xml_file_handling(self):
        """Test handling of larger XML files."""
        # Create a larger XML file with many sections
        large_xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<legislation>\n']

        # Add many sections
        for i in range(100):
            section_xml = f"""    <section id="section{i}">
        <title>Section {i}</title>
        <content>This is the content for section {i}. It contains various legal provisions and requirements that must be followed.</content>
    </section>
"""
            large_xml_parts.append(section_xml)

        large_xml_parts.append("</legislation>")
        large_xml = "".join(large_xml_parts)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(large_xml)
            temp_path = f.name

        try:
            soup = load_xml_file_to_soup(temp_path)

            # Verify all sections were parsed
            sections = soup.find_all("section")
            assert len(sections) == 100

            # Test random access to sections
            section_50 = soup.find("section", {"id": "section50"})
            assert section_50 is not None
            assert "Section 50" in section_50.find("title").text

            # Test that content is preserved
            assert "section 50" in section_50.find("content").text.lower()

        finally:
            os.unlink(temp_path)


# Fixtures for integration tests
@pytest.fixture(scope="session")
def elasticsearch_client():
    """Session-scoped fixture for Elasticsearch client."""
    client = get_elasticsearch_client()
    if client:
        yield client
    else:
        pytest.skip("Elasticsearch not available for integration tests")


@pytest.fixture
def temp_xml_file():
    """Fixture that creates and cleans up temporary XML files."""
    temp_files = []

    def create_temp_xml(content):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            temp_files.append(f.name)
            return f.name

    yield create_temp_xml

    # Cleanup
    for temp_file in temp_files:
        try:
            os.unlink(temp_file)
        except FileNotFoundError:
            pass
