# Lex

UK legal API for AI agents and researchers. Access comprehensive UK legislation data with semantic search and Model Context Protocol integration.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## What is Lex?

Lex provides programmatic access to 8.4M+ UK legal documents - legislation, amendments, and explanatory notes - with hybrid semantic search.

**This is an experimental service and should not be used as a production dependency.**

### Dataset Coverage

- **Legislation** - 220K Acts and Statutory Instruments (1267-present, complete from 1963)
- **Amendments** - 892K legislative changes and modifications
- **Explanatory Notes** - 89K notes providing legislative context
- **Case Law** - 70K judgments and 4.7M paragraphs (temporarily disabled pending TNA licence)
- **PDF Digitisation** - Historical legislation (pre-1963) digitised using AI

### What Can You Build?

- **Legal Research** - Find relevant legislation in seconds
- **Policy Analysis** - Track legislative changes over time
- **AI Grounding** - Ground AI assistants in authoritative UK legal sources

## MCP Integration

Connect AI assistants to Lex via Model Context Protocol. See the [live documentation](https://lex.lab.i.ai.gov.uk/docs) for setup instructions for:

- Claude Desktop
- Claude Code
- Cursor
- Microsoft Copilot Studio
- VS Code + GitHub Copilot

## Local Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose
- Azure OpenAI credentials

### Quick Start

```bash
# Clone and setup
git clone https://github.com/i-dot-ai/lex.git && cd lex
cp .env.example .env  # Add your Azure OpenAI keys

# Start services and load sample data
docker compose up -d
make ingest-all-sample

# Visit http://localhost:8000/docs for API documentation
```

### Data Loading

```bash
# Quick samples (recommended for testing)
make ingest-legislation-sample
make ingest-all-sample

# Full datasets (production use)
make ingest-legislation-full
make ingest-all-full

# Create indexes for fast filtering
uv run python scripts/create_payload_indexes.py
```

### Development Commands

```bash
make install          # Install dependencies
make test             # Run tests
make run              # Start API locally (without Docker)
uv run ruff format .  # Format code
```

## Architecture

```
lex/
├── src/
│   ├── lex/              # Data pipeline (scraping, parsing, indexing)
│   └── backend/          # API server (FastAPI + MCP)
├── infrastructure/       # Azure Bicep templates and deploy scripts
├── scripts/              # Maintenance, migration, and export utilities
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Documentation

- [System Architecture](docs/system-architecture.md) - Start here for the full picture
- [Deployment Guide](docs/deployment.md)
- [Operations Runbook](docs/operations-runbook.md)
- [Data Pipeline Guide](src/lex/README.md)
- [API Reference](src/backend/README.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributing](CONTRIBUTING.md)

## Acknowledgements

Built with support from [The National Archives](https://www.nationalarchives.gov.uk/) and [Ministry of Justice](https://www.gov.uk/government/organisations/ministry-of-justice).

## License

MIT - See [LICENSE](LICENSE) for details.
