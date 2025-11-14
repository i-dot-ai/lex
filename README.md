# ⚖️ Lex

**UK Legal Data API** - Search 2M+ laws, cases, and legal documents via REST API or MCP tools.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://docs.docker.com/compose/install/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🚀 Quick Start Options

### Option 1: Use Public API (No Setup)

Skip local setup and use the public API for development:

```bash
# Test the public API
curl -X POST https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io/legislation/search \
  -H "Content-Type: application/json" \
  -d '{"query": "data protection", "limit": 5}'
```

**⚠️ Experimental**: Public API is for development/testing only. Not guaranteed to be available.

### Option 2: Frontend Only (Use Public API + Local UI)

Run the frontend locally pointing to the public API:

```bash
# 1. Clone and setup frontend
git clone https://github.com/i-dot-ai/lex.git && cd lex/app
bun install

# 2A. Configure for public API
echo 'NEXT_PUBLIC_API_URL=https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io' > .env.local

# 3. Start frontend
bun dev

# 4. Open web interface  
open http://localhost:3000
```

### Option 3: Full Local Setup (Complete System)

#### 3A. Local Frontend + Public API Backend

```bash
# 1. Setup frontend (as above)
git clone https://github.com/i-dot-ai/lex.git && cd lex
cp .env.example .env

# 2. Setup frontend pointing to public API
cd app && bun install
echo 'NEXT_PUBLIC_API_URL=https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io' > .env.local
bun dev

# Frontend runs at http://localhost:3000
```

#### 3B. Local Frontend + Local Backend + Data

```bash
# 1. Clone and setup
git clone https://github.com/i-dot-ai/lex.git && cd lex
cp .env.example .env  # Add your Azure OpenAI keys

# 2. Start backend services
docker compose up -d

# 3. Load sample data (⚡ ~5 min)
make ingest-all-sample

# 4. Start frontend (separate terminal)
cd app && bun install 
# .env.local defaults to http://localhost:8000
bun dev

# 5. Open web interface
open http://localhost:3000
```

**Complete system**: Web UI at <http://localhost:3000> and API docs at <http://localhost:8000/docs> 📚

## 🎯 What You Get

- **125K+** UK laws (1963-present)
- **2.4M+** case sections (2001-present)
- **980K+** law sections with semantic search
- **82K+** explanatory notes
- **30K+** full court cases

*📈 Stats from October 2025 - continuously growing with new legislation and cases*

All searchable via:

- 🌐 **Web Interface** - Next.js frontend with modern UI
- 🔌 **REST API** - FastAPI with full OpenAPI docs
- 🤖 **MCP Tools** - Direct integration with Claude Desktop
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

### Get specific act

```bash
curl -X POST http://localhost:8000/legislation/lookup \
  -H "Content-Type: application/json" \
  -d '{
    "legislation_type": "ukpga",
    "year": 2018,
    "number": 12
  }'
```

## 🤖 MCP Integration

**Option 1: Public API** (no local setup required):

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

**Option 2: Local setup**:

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

## 📦 Data Loading Options

### Quick samples for testing

```bash
make ingest-legislation-sample      # ⚡ 5 min - Recent laws
make ingest-caselaw-sample         # ⚡ 5 min - Recent cases
make ingest-all-sample            # ⚡ 15 min - Everything sampled
```

### Full datasets

```bash
make ingest-legislation-full      # ☕ 2 hrs - All laws (1963+)
make ingest-caselaw-full         # 🌙 8 hrs - All cases (2001+)
make ingest-all-full            # 🌙 24 hrs - Complete database
```

### Optimize query performance

After ingesting data, create payload indexes for fast filtering:

```bash
uv run python scripts/create_payload_indexes.py  # Creates indexes on filtered fields
```

This improves filter query performance from 60s → 10ms (6000x faster). Indexes build in background (~2-5 minutes).

## 🏗️ Architecture

```
lex/
├── src/
│   ├── lex/          # Data pipeline (scraping → parsing → indexing)
│   └── backend/      # API server (FastAPI + MCP)
├── tools/            # Export utilities (Parquet/JSONL)
└── data/            # Local storage
```

Each component handles 4 document types:

- **Legislation** - Primary & secondary laws
- **Caselaw** - Court judgments
- **Explanatory Notes** - Legislative context
- **Amendments** - Changes over time

## 🔧 Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose
- Azure OpenAI credentials

### Local development

```bash
# Install dependencies
make install

# Run tests
make test

# Format code
uv run ruff format .

# Start API locally (without Docker)
make run
```

### Cloud Qdrant

Switch between local and cloud Qdrant in `.env`:

```bash
USE_CLOUD_QDRANT=false  # Local (default)
USE_CLOUD_QDRANT=true   # Cloud
```

Then restart: `docker compose restart backend`

### Export data

```bash
# List available indices
python tools/export_data.py list

# Export to Parquet (for ML/analytics)
python tools/export_data.py export --index lex-dev-legislation --format parquet

# Export to JSONL (for streaming)
python tools/export_data.py export --index lex-dev-caselaw --format jsonl
```

## 💾 Storage Requirements

### Current Dataset Size: ~70GB (and growing)

| Collection | Documents | Storage | Notes |
|------------|-----------|---------|-------|
| Caselaw Sections | ~2.4M | ~35GB | Largest - full case sections with hybrid vectors |
| Legislation Sections | ~980K | ~18GB | Law sections with semantic search |
| Caselaw (Full) | ~30K | ~10GB | Complete court judgments |
| Explanatory Notes | ~82K | ~1.5GB | Legislative context documents |
| Legislation (Metadata) | ~125K | ~850MB | Law metadata only |
| Embedding Cache | ~220K | ~1.3GB | Performance optimization |
| **Total** | **~3.8M** | **~70GB** | *Growing with new legislation & cases* |

### Hosting Requirements

- **Minimum**: 100GB disk space (allows for growth)
- **Recommended**: 150GB+ disk space
- **Memory**: 8GB RAM (Qdrant can use up to 8GB, backend ~2GB)
- **Note**: Dataset grows continuously as new legislation is enacted and cases are published

### Ingestion Times (Full Dataset)

- Legislation: ~2-3 hours
- Legislation Sections: ~2-3 days
- Caselaw: ~1-2 days
- Caselaw Sections: ~5-6 days
- **Total**: ~10 days for complete dataset (3.8M+ documents with embeddings)

## 🐛 Troubleshooting

### Qdrant or services won't start

```bash
# Check memory limits and clean up
docker system prune
docker compose down && docker compose up -d
```

### Slow ingestion

```bash
# Adjust batch size in .env
PIPELINE_BATCH_SIZE=50  # Lower for less memory
```

### API returns no results

```bash
# Check collections are populated
curl http://localhost:6333/collections | jq '.result.collections[] | {name, points_count}'
```

## 📚 Documentation

- [Data Pipeline Guide](src/lex/README.md) - Ingestion, parsing, custom workflows
- [API Reference](src/backend/README.md) - Endpoints, search queries, integration
- [Changelog](CHANGELOG.md) - Version history
- [Contributing](CONTRIBUTING.md) - Development guidelines

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## ⚠️ Limitations

- Alpha release - APIs may change
- PDF-only legislation digitisation is WIP

## 🙏 Acknowledgements

Built with generous support from [The National Archives](https://www.nationalarchives.gov.uk/) and [Ministry of Justice](https://www.gov.uk/government/organisations/ministry-of-justice).

## 📄 License

MIT - See [LICENSE](LICENSE) for details.
