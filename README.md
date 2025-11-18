# ⚖️ Lex

**UK Legal Data API** - Search millions of laws, cases, and legal documents via REST API or MCP tools.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://docs.docker.com/compose/install/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🚀 Quick Start

### Try the Public API

```bash
# Test the live API (no setup required)
curl -X POST https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io/legislation/search \
  -H "Content-Type: application/json" \
  -d '{"query": "data protection", "limit": 5}'
```

**⚠️ Note**: Public API is experimental and not guaranteed to be available.

### Run Locally (Frontend Only)

```bash
git clone https://github.com/i-dot-ai/lex.git && cd lex/app
bun install && bun dev
# Visit http://localhost:3000
```

### Full Local Setup

```bash
# 1. Clone and setup environment
git clone https://github.com/i-dot-ai/lex.git && cd lex
cp .env.example .env  # Add your Azure OpenAI keys

# 2. Start services and load sample data
docker compose up -d
make ingest-all-sample

# 3. Start frontend (separate terminal)
cd app && bun install && bun dev

# Visit http://localhost:3000 for web UI
# Visit http://localhost:8000/docs for API docs
```

## 🎯 What You Get

Comprehensive UK legal database including:

- **Legislation** - Acts and Statutory Instruments (1963-present)
- **Case Law** - Court judgments and decisions (2001-present) 
- **Explanatory Notes** - Legislative context and guidance
- **Amendments** - Changes and modifications over time

All searchable via:

- 🌐 **Web Interface** - Modern Next.js frontend
- 🔌 **REST API** - FastAPI with full OpenAPI documentation  
- 🤖 **MCP Tools** - Direct integration with AI assistants
- 🔍 **Semantic Search** - Powered by Azure OpenAI embeddings

## 💻 API Examples

### Search legislation

```bash
curl -X POST http://localhost:8000/legislation/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "year_from": 2020,
    "limit": 3
  }'
```

### Find case law

```bash
curl -X POST http://localhost:8000/caselaw/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "breach of contract",
    "court": ["uksc", "ewca"],
    "is_semantic_search": true
  }'
```

## 🤖 MCP Integration

Add to your Claude Desktop configuration:

**Public API** (no local setup):
```json
{
  "mcpServers": {
    "lex": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io/mcp"]
    }
  }
}
```

**Local setup**:
```json
{
  "mcpServers": {
    "lex": {
      "command": "uvx", 
      "args": ["mcp-proxy", "http://localhost:8000/mcp"]
    }
  }
}
```

Then ask Claude: *"Search for UK laws about data protection from 2018"*

## 📦 Data Loading

### Quick samples (recommended for testing)
```bash
make ingest-legislation-sample    # Recent laws
make ingest-caselaw-sample       # Recent cases  
make ingest-all-sample          # Everything sampled
```

### Full datasets (production use)
```bash
make ingest-legislation-full    # All legislation (1963+)
make ingest-caselaw-full       # All case law (2001+)
make ingest-all-full          # Complete database
```

### Optimize performance
```bash
# Create indexes for fast filtering (run after data loading)
uv run python scripts/create_payload_indexes.py
```

## 🏗️ Architecture

```
lex/
├── src/
│   ├── lex/          # Data pipeline (scraping → parsing → indexing)
│   └── backend/      # API server (FastAPI + MCP)
├── app/              # Next.js frontend
├── tools/            # Export utilities (Parquet/JSONL)
└── data/            # Local storage
```

## 🔧 Development

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 
- Docker & Docker Compose
- Azure OpenAI credentials

### Commands
```bash
make install          # Install dependencies
make test            # Run tests  
make run             # Start API locally (without Docker)
uv run ruff format . # Format code
```

### Export data
```bash
# Export to Parquet (for ML/analytics)
python tools/export_data.py export --index lex-dev-legislation --format parquet

# Export to JSONL (for streaming)
python tools/export_data.py export --index lex-dev-caselaw --format jsonl
```

## 🐛 Troubleshooting

### Services won't start
```bash
docker system prune
docker compose down && docker compose up -d
```

### API returns no results
```bash
# Check collections are populated
curl http://localhost:6333/collections | jq '.result.collections[] | {name, points_count}'
```

### Performance issues
```bash
# Adjust batch size in .env
PIPELINE_BATCH_SIZE=50  # Lower for less memory usage
```

## 📚 Documentation

- [Data Pipeline Guide](src/lex/README.md) - Ingestion, parsing, custom workflows
- [API Reference](src/backend/README.md) - Endpoints, search queries, integration
- [Contributing](CONTRIBUTING.md) - Development guidelines

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## ⚠️ Limitations

- Alpha release - APIs may change
- PDF-only legislation digitisation is work in progress

## 🙏 Acknowledgements

Built with support from [The National Archives](https://www.nationalarchives.gov.uk/) and [Ministry of Justice](https://www.gov.uk/government/organisations/ministry-of-justice).

## 📄 License

MIT - See [LICENSE](LICENSE) for details.