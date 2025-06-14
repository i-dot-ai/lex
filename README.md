# ⚖️ Lex


Lex is a comprehensive legislative service that downloads, parses, and indexes legislation, explanatory notes, amendments, and caselaw for subsequent search via an OpenAPI backend and MCP server.

#### Acknowledgements
This project would not have been possible without the generous support of [The National Archives](https://www.nationalarchives.gov.uk/) and previous work from the [Ministry of Justice](https://www.gov.uk/government/organisations/ministry-of-justice). They have been heavily involved in the development of Lex and helping it get to where it is today.

## Project Structure

Lex is split into two key components. These have their own detailed documentation to cover in depth the [ingestion](src/lex/README.md) and [backend](src/backend/README.md). Each of these is then divided into legislation, caselaw, explanatory notes, and amendments.

```
src/
├── lex/             # Core library for legislative processing
└── backend/         # FastAPI and FastMCP backend service
```

## Quickstart Guide
This guide will walk you through setting up a FastAPI backend and MCP server from scratch and populating it with some initial datasets.

### Prerequisites
Make sure you have the following installed before going through the next steps. Installation guides for each are linked.

- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [python 3.12+](https://docs.astral.sh/uv/guides/install-python/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer)
- [docker and docker dompose](https://docs.docker.com/compose/install/)

This project uses OpenAI via Azure rather than calling OpenAI services directly. If you have an OpenAI API key and want to use this directly consider creating an issue or making a pull request.

### Quick Start

**1. Clone this repository:**
```bash
git clone https://github.com/i-dot-ai/lex.git
cd lex
```

**2. Configure environment variables:**

Copy the `.env.example` script and add your environment keys.
```bash
cp .env.example .env
```


**3. Start the development environment using Docker:**
```bash
docker compose up -d
```
This will setup four containers:
   - Elasticsearch at http://localhost:9200
   - Kibana at http://localhost:5601
   - Backend API at http://localhost:8000, initially empty but we'll add some data
   - A pipeline container for data processing. This doesn't expose any endpoints.

**4. Load some initial datasets using the Makefile:**
```bash
# Load sample data (recommended for getting started)
make ingest-legislation-sample
make ingest-legislation-section-sample
make ingest-caselaw-sample
...
```
We've chosen to load samples of legislation, legislation sections, and caselaw. These sample commands load a limited subset of recent data (2020-current year for legislation, 50 documents limit).

Each command does a fair bit of work behind the scenes. It scrapes the data from The National Archives, parses it to json, uploads it to Elasticsearch (which creates embeddings for the semantic text fields). This will process significant data behind the scenes. For this quickstart only a small subset of data is downloaded - it'll take around 5 minutes to complete.

To index complete datasets, use the `-full` commands which can take up to 24hrs. These commands ingest all legislation types from 1963 onwards and caselaw from 2001 onwards. To understand how to index all the data you're interested in explore the [ingestion README](src/lex/README.md).

**5. Run an MCP client**

That's it. You've now got a backend hosted at http://localhost:8000 (view the docs at http://localhost:8000/docs and the MCP server at http://localhost:8000/mcp). If you have an MCP client such as Claude Desktop you can add this json to the mcp configuration file and test the tools. You'll need `uv` installed globally for the `uvx` command to work.

```json
{
  "mcpServers": {
    "lex": {
      "command": "uvx",
      "args": [
        "mcp-proxy",
        "http://localhost:8000/mcp"
      ]
    }
  }
}
```

## Quick Data Loading

The Makefile provides convenient commands for loading different types of legal data:

### Sample Data (Quick Start)
```bash
# Individual data types - limited samples for testing
make ingest-legislation-sample          # Primary legislation (ukpga only, 2020-current year, limit 50)
make ingest-legislation-section-sample  # Individual sections of legislation
make ingest-caselaw-sample             # Court judgments (limit 50)
make ingest-caselaw-section-sample     # Individual sections of caselaw
make ingest-explanatory-note-sample    # Documents explaining legislation
make ingest-amendment-sample           # Changes to legislation

# Load sample of everything
make ingest-all-sample
```

### Full Data (Complete Dataset)
```bash
# Individual data types - all available data
make ingest-legislation-full          # ALL legislation types (1963-current year)
make ingest-legislation-section-full  # ALL legislation sections (1963-current year)
make ingest-caselaw-full             # ALL court judgments (2001-current year)
make ingest-caselaw-section-full     # ALL caselaw sections (2001-current year)
make ingest-explanatory-note-full    # ALL explanatory notes (1963-current year)
make ingest-amendment-full           # ALL amendments (1963-current year)

# Load everything (warning: this takes 24+ hours)
make ingest-all-full
```

Note: Legislation data is available from 1963 onwards, while caselaw data is available from 2001 onwards. The sample commands are intended to get you up and running quickly with recent data. The full commands will ingest all available data but require significant time and resources.

## Next Steps

After getting the basic system running:

1. **For API Usage**: See the [Backend README](src/backend/README.md) for detailed API documentation, search examples, and integration patterns

2. **For Data Processing**: See the [Lex README](src/lex/README.md) for:
   - Ingesting more datasets
   - Elasticsearch configuration (local vs cloud)
   - Custom data ingestion workflows
   - Architecture and extension guides

3. **For Development**: Both component READMEs contain development setup instructions and architectural details

## Development

### Testing

Run tests from the respective component directories:

```bash
uv run pytest
```

The tests are integration tests focused on validating the entire pipeline, plus XML parsing validation tests. You'll need to have the backend running and have ingested certain documents for the tests to work.

## Support

For support, please [open an issue](https://github.com/i-dot-ai/lex/issues) on our GitHub repository.
