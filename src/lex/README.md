# Lex Core

This module provides the core functionality for processing legislation, explanatory notes, amendments and caselaw into Elasticsearch. This README will walk through how to use this functionality.

## Architecture Overview

Lex lets you process legislation, explanatory notes, amendments and caselaw. The code for each of these is outlined in the respective subdirectories.

Within each individual subdirectory Lex follows a consistent data flow across all document types:

1. **Scrapers** - Download and extract raw content (HTML/XML) from legislation websites. For legislation we also provide **Loaders** to process legislation directly from file.
2. **Parsers** - Transform raw content into structured Pydantic models. These are defined in the `models.py` file in each 
3. **Pipeline** - Process and upload models to Elasticsearch
4. **Elasticsearch** - Indexes and provides vector embeddings for semantic search

### Data Flow

All document types follow the same consistent scraper→parser→pipeline architecture:

```
                   ┌─────────┐          ┌─────────┐          ┌──────────┐          ┌─────────────────┐
                   │         │          │         │          │          │          │                 │
Raw Content ───────► Scraper ├──Soup───► Parser   ├──Models──► Pipeline ├──JSON────► Elasticsearch   │
                   │         │          │         │          │          │          │ (with automatic │
                   └─────────┘          └─────────┘          └──────────┘          │   embedding)    │
                                                                                   └─────────────────┘
```

**Note**: Explanatory notes have a small performance trade-off as their parser requires additional HTTP requests to fetch content across multiple pages, but this maintains API consistency across all document types.

### Available Models

The system processes several types of legal documents:

- **Legislation**: Primary legislation documents
- **Legislation Sections**: Individual sections of legislation
- **Explanatory Notes**: Documents explaining legislation
- **Amendments**: Changes to legislation
- **Caselaw**: Court judgments and decisions
- **Caselaw Sections**: Individual sections of caselaw documents

Each model is uploaded to its own Elasticsearch index.

## Getting Started

The root README walks through uploading a sample set of documents. This README walks through the customisation options available and how to bulk index legislation. It's recommended to initially index only a subset of legislation and caselaw for testing. Indexing all available legislation, caselaw, explanatory notes and amendments will currently require several tens of hours of scraping, parsing, and indexing.

### Quickstart reminder

As a reminder, the fastest way to get started is using the provided Makefile commands:

```bash
# Start the Docker environment
make docker-up

# Load individual data types
make ingest-legislation         # Primary legislation documents
make ingest-legislation-section # Individual sections of legislation  
make ingest-caselaw             # Court judgments and decisions
make ingest-caselaw-section     # Individual sections of caselaw
make ingest-explanatory-note    # Documents explaining legislation
make ingest-amendment           # Changes to legislation

# Load all data types with optimal settings
make ingest-all
```

## Command Reference
These make commands are fine for getting up and running, but they don't provide any fine grained control. For more control over the ingestion process we can use the command reference directly.

### Main Entry Point

The main entry point is `src/lex/main.py`. This provides a unified interface to process all document types.

### Command-Line Options

- `-m, --model`: Data model to process (legislation, legislation-section, explanatory-note, amendment, caselaw, caselaw-section)
- `-y, --years`: Year(s) of legislation to include (e.g., 2022 or multiple years as 2022 2023, or 2020-2025)
- `-t, --types`: Legislation types to include (e.g., ukpga, uksi, etc.). When indexing caselaw this also accepts UK courts (e.g. uksc, ukpc, etc.)
- `-l, --limit`: Limit the number of documents to process. For the `legislation-section` and `caselaw-section` endpoints this limits the number of 
- `--batch-size`: Number of documents to process in each batch
- `--non-interactive`: Skip confirmation prompts
- `--from-file`: [Legislation only] Load documents from local files instead of scraping from the web

### Usage Patterns

There are three ways to use this command-line, that all do the same thing under the hood. We recommend using Docker although using uv can be faster if you're iterating locally. We'll only give docker examples in this README but the syntax is identical if using the other methods. Always run these commands from the root directory.

**Docker:**
```bash
docker compose exec pipeline uv run src/lex/main.py -m [model] -y [years] -t [types] [options]
```

**Direct Python:**
```bash
python src/lex/main.py -m [model] -y [years] -t [types] [options]
```

NB. if you are using python directly you'll need a virtual environment. Run `uv sync` to create one.

**With uv:**
```bash
uv run src/lex/main.py -m [model] -y [years] -t [types] [options]
```

### Using Docker Services

Ensure the docker services are running:
```bash
docker-compose up -d
```

Then we can use this container to upload legislation

**Legislation Examples:**
```bash
# Upload UK Primary General Acts from 2020 to 2025
docker compose exec pipeline uv run src/lex/main.py -m legislation --non-interactive --types ukpga --years 2020-2025

# Upload individual sections from 2020-2022, limit to 100 pieces.
docker compose exec pipeline uv run src/lex/main.py -m legislation-section --non-interactive --types ukpga --years 2020 2021 2022 --limit 100
```

**Explanatory Notes:**
```bash
docker compose exec pipeline uv run src/lex/main.py -m explanatory-note --non-interactive --types ukpga --years 2022 --limit 100
```

**Amendments:**
```bash
docker compose exec pipeline uv run src/lex/main.py -m amendment --non-interactive --types ukpga --years 2013 --limit 100
```

**Caselaw:**
```bash
# Court of Appeal cases from 2018
docker compose exec pipeline uv run src/lex/main.py -m caselaw --non-interactive -t ewca --years 2018

# Family Court sections from 2016-2018
docker compose exec pipeline uv run src/lex/main.py -m caselaw-section --non-interactive --types ewfc --years 2016 2017-2018 --limit 100
```

### Using Pre-Downloaded Statute Book Data

For faster processing or offline work, you can use pre-downloaded "Statute Book Data" from research.legislation.gov.uk instead of scraping content in real-time. This is highly recommended especially for bulk legislation indexing jobs.

#### Download and Setup

1. **Download Statute Book Data**:
   - Visit [research.legislation.gov.uk](https://research.legislation.gov.uk). You will need to request access unless already provided from The National Archives.
   - Download the Statute Book Data archive and select for the legislation type.
   - We are hoping to provide a seperate download of this legislation, although it doesn't yet exist.

2. **Extract to Correct Location**:
   ```bash
   # Create the directory structure
   mkdir -p data/raw/legislation
   
   # Extract the downloaded archive to this location
   # The structure should be: data/raw/legislation/{year}/{legislation-type}-{year}-{number}.xml
   unzip statute-book-data.zip -d data/raw/legislation/
   ```

3. **Expected Directory Structure**:
   ```
   data/raw/legislation/
   ├── 2020/
   │   ├── ukpga-2020-1.xml
   │   ├── ukpga-2020-2.xml
   │   └── uksi-2020-100.xml
   ├── 2021/
   │   ├── ukpga-2021-1.xml
   │   └── ...
   └── 2022/
       └── ...
   ```

   It's important the file structure matches that shown above otherwise the `LegislationLoader` will not work.

#### Using the From-File Method

Once you have the data in place, use the `--from-file` argument to process legislation from local files instead of scraping. This can be used as a drop in replacement.

**Docker Commands:**
```bash
# Process legislation metadata from files
docker compose exec pipeline uv run src/lex/main.py -m legislation --from-file --non-interactive --types ukpga --years 2020 2021 2022

# Process legislation sections from files
docker compose exec pipeline uv run src/lex/main.py -m legislation-section --from-file --non-interactive --types ukpga --years 2020 2021 2022 --limit 100
```

**Note**: The `--from-file` option is only available for `legislation` and `legislation-section` models. Other document types (caselaw, explanatory notes, amendments) still require web scraping.


## Elasticsearch Setup

This project can be configured to use either a local Elasticsearch instance or Elastic Cloud.

**Local Elasticsearch (Default)**
- Run `docker-compose up` to start Elasticsearch and Kibana locally
- Access Kibana at http://localhost:5601
- Elasticsearch will be available at http://localhost:9200

**Elastic Cloud**
- Create a deployment on [Elastic Cloud](https://cloud.elastic.co)
- Copy `.env-example` to `.env` and configure:
  ```
  ELASTIC_MODE=cloud
  ELASTIC_CLOUD_ID=your-deployment-id:region
  ELASTIC_API_KEY=your-api-key
  # Or use username/password instead
  # ELASTIC_USERNAME=elastic
  # ELASTIC_PASSWORD=your-password
  ```
- Run `docker-compose up` (will not start local Elasticsearch)

### Embeddings

Embedding is automatically handled by Elasticsearch. Any content uploaded to the `legislation-section`, `explanatory-note`, `caselaw`, and `caselaw-section` indices will be automatically indexed using the provided credentials. The `legislation` and `amendment` indices do not embed any text. Lex doesn't have any dependencies on OpenAI or other LLM packages. All this work is handled by Elasticsearch.

## HTTP Caching

Although most content is taken from The National Archives, we implement HTTP caching to minimize unnecessary requests to external sources. When downloading content from legislation.gov.uk and other legal data sources, the scrapers will only make HTTP requests if the content is not already cached locally. This significantly improves performance during development and reduces load on external services, especially when re-running ingestion processes or processing large datasets.

## Checkpoint System and Resume Capability

Lex includes a sophisticated checkpointing system that enables reliable processing of large datasets with automatic resume capability.

### Key Features
- **Persistent Progress Tracking**: Automatically saves progress for each year/type combination
- **Intelligent Resume**: Continues from exactly where processing was interrupted  
- **Error Recovery**: Distinguishes between retryable and permanent failures
- **Memory Efficiency**: Skips already-processed documents and combinations

### Using Checkpoints
Checkpointing is enabled by default. If processing is interrupted:

```bash
# Simply re-run the same command - it will resume automatically
docker compose exec pipeline uv run src/lex/main.py -m legislation --types ukpga --years 2020-2025
```

### Managing Checkpoints
```bash
# Clear checkpoint state to restart from beginning
docker compose exec pipeline uv run src/lex/main.py -m legislation --types ukpga --years 2020-2025 --clear-checkpoint

# Checkpoints are stored persistently and survive container restarts
```

### How It Works
The system tracks:
- Successfully processed document URLs
- Failed URLs with error details  
- Current position in each year/type combination
- Completed combinations (fully processed)

This enables processing of large datasets (10,000+ documents) over multiple sessions with confidence.

## Extending the System

To add support for new document types, you can follow one of two patterns:

#### Standard Pattern (for all document types)

1. Create a new scraper class inheriting from `LexScraper`
2. Create a parser class inheriting from `LexParser`
3. Define Pydantic models for the document type
4. Add pipeline function to process and upload the documents
5. Update the `index_mapping` in `main.py`

**Note**: For document types that span multiple pages (like explanatory notes), the parser can make additional HTTP requests during the parsing phase while still maintaining the consistent scraper→parser→pipeline architecture.

## Architecture Details

#### Scrapers

Scrapers download raw content from external sources:

- `LegislationScraper`: Downloads legislation XML from legislation.gov.uk
- `AmendmentScraper`: Downloads amendments to legislation from tables on legislation.gov.uk
- `CaselawScraper`: Downloads caselaw HTML from various sources
- `ExplanatoryNoteScraper`: Downloads explanatory notes from multiple pages on legislation.gov.uk

Each scraper returns BeautifulSoup objects representing the raw content.

#### Parsers

Parsers transform raw BeautifulSoup content into structured Pydantic models:

- `LegislationParser`: Creates `Legislation` models from XML
- `LegislationSectionParser`: Creates `LegislationSection` models from XML
- `AmendmentParser`: Creates `Amendment` models from HTML tables
- `CaselawParser`: Creates `Caselaw` models from HTML
- `CaselawSectionParser`: Creates `CaselawSection` models from HTML
- `ExplanatoryNoteParser`: Creates `ExplanatoryNote` models from HTML (with additional HTTP requests for multi-page content)

#### Models

The system uses Pydantic models to represent legal documents:

- Base classes: `LexModel`, `EmbeddableModel`
- Legislation models: `Legislation`, `LegislationSection`, `Provision`, etc.
- Caselaw models: `Caselaw`, `CaselawSection`, etc.

#### Pipeline

The pipeline orchestrates the data flow:

For all document types (Legislation, Amendments, Caselaw, Explanatory Notes):
1. Calls the appropriate scraper to get content (BeautifulSoup objects)
2. Passes the content to the parser to create models
3. Uploads the models to Elasticsearch using the document handling utilities
4. Elasticsearch automatically handles embedding and indexing

#### Core Utilities

- `document.py`: Manages batching, uploading, and updating documents
- `clients.py`: Provides Elasticsearch client configuration
- `index.py`: Handles index creation and management

