# 🌐 Lex Backend

Fast, modern API for UK legal data - search 2M+ laws, cases, and legal documents via REST or MCP.

## 🚀 Quick Start

```bash
# API is available at
http://localhost:8000       # Main API
http://localhost:8000/docs  # Interactive docs (Swagger)
http://localhost:8000/redoc # Alternative docs (ReDoc)
```

## 💻 API Examples (Copy & Paste Ready)

### 📚 Legislation

#### Search by title
```bash
curl -X POST http://localhost:8000/legislation/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "data protection",
    "year_from": 2015,
    "limit": 5
  }'
```

#### Lookup specific act
```bash
curl -X POST http://localhost:8000/legislation/lookup \
  -H "Content-Type: application/json" \
  -d '{
    "legislation_type": "ukpga",
    "year": 2018,
    "number": 12
  }'
```

#### Search sections (semantic)
```bash
curl -X POST http://localhost:8000/legislation/section/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "personal data processing",
    "limit": 10
  }'
```

#### Get full text
```bash
curl -X POST http://localhost:8000/legislation/text \
  -H "Content-Type: application/json" \
  -d '{
    "legislation_id": "http://www.legislation.gov.uk/id/ukpga/2018/12",
    "include_schedules": false
  }'
```

### ⚖️ Caselaw

#### Text search
```bash
curl -X POST http://localhost:8000/caselaw/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "negligence",
    "court": ["uksc", "ewca"],
    "is_semantic_search": false,
    "limit": 5
  }'
```

#### Semantic search (AI-powered)
```bash
curl -X POST http://localhost:8000/caselaw/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "employer liability for remote work injuries",
    "is_semantic_search": true,
    "year_from": 2020,
    "limit": 5
  }'
```

#### Find cases citing legislation
```bash
curl -X POST http://localhost:8000/caselaw/reference/search \
  -H "Content-Type: application/json" \
  -d '{
    "reference_id": "http://www.legislation.gov.uk/id/ukpga/2018/12",
    "reference_type": "legislation",
    "size": 10
  }'
```

### 📝 Explanatory Notes

#### Search notes
```bash
curl -X POST http://localhost:8000/explanatory_note/section/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "GDPR implementation",
    "size": 5
  }'
```

#### Get notes for legislation
```bash
curl -X POST http://localhost:8000/explanatory_note/legislation/lookup \
  -H "Content-Type: application/json" \
  -d '{
    "legislation_id": "http://www.legislation.gov.uk/id/ukpga/2018/12",
    "limit": 10
  }'
```

### 🔄 Amendments

#### Find amendments to legislation
```bash
curl -X POST http://localhost:8000/amendment/search \
  -H "Content-Type: application/json" \
  -d '{
    "legislation_id": "http://www.legislation.gov.uk/id/ukpga/1998/29",
    "search_amended": true,
    "size": 5
  }'
```

## 📋 Complete Endpoint Reference

| Endpoint | Method | Purpose | Key Parameters |
|----------|---------|---------|----------------|
| `/legislation/search` | POST | Search acts by title | `query`, `year_from`, `year_to`, `types` |
| `/legislation/lookup` | POST | Get specific act | `legislation_type`, `year`, `number` |
| `/legislation/section/search` | POST | Search law sections | `query`, `limit` |
| `/legislation/section/lookup` | POST | Get act sections | `legislation_id`, `limit` |
| `/legislation/text` | POST | Get full text | `legislation_id`, `include_schedules` |
| `/caselaw/search` | POST | Search cases | `query`, `court`, `is_semantic_search` |
| `/caselaw/reference/search` | POST | Find citing cases | `reference_id`, `reference_type` |
| `/explanatory_note/section/search` | POST | Search notes | `query`, `size` |
| `/explanatory_note/legislation/lookup` | POST | Get notes for act | `legislation_id` |
| `/amendment/search` | POST | Find amendments | `legislation_id`, `search_amended` |
| `/healthcheck` | GET | API health | - |

## 🎯 Common Search Patterns

### Find recent data protection laws
```bash
curl -X POST http://localhost:8000/legislation/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "data protection GDPR",
    "year_from": 2018,
    "types": ["ukpga", "uksi"]
  }'
```

### Get Supreme Court precedents on contracts
```bash
curl -X POST http://localhost:8000/caselaw/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "breach of contract consideration",
    "court": ["uksc"],
    "is_semantic_search": true
  }'
```

### Track legislative changes
```bash
# 1. Get the original act
curl -X POST http://localhost:8000/legislation/lookup \
  -H "Content-Type: application/json" \
  -d '{"legislation_type": "ukpga", "year": 1998, "number": 29}'

# 2. Find all amendments to it
curl -X POST http://localhost:8000/amendment/search \
  -H "Content-Type: application/json" \
  -d '{
    "legislation_id": "http://www.legislation.gov.uk/id/ukpga/1998/29",
    "search_amended": true
  }'
```

## 🔌 MCP Integration

The backend includes built-in MCP support for AI assistants via `fastapi-mcp`.

### Setup for Claude Desktop

1. **Start the API server** (in a separate terminal):
   ```bash
   make run
   # or: uv run src/backend/main.py
   ```

2. **Find the full path to mcp-proxy**:
   ```bash
   which mcp-proxy
   # Example output: /Users/username/.pyenv/shims/mcp-proxy
   ```

3. **Configure Claude Desktop** at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
   ```json
   {
     "mcpServers": {
       "lex": {
         "command": "/Users/username/.pyenv/shims/mcp-proxy",
         "args": ["http://127.0.0.1:8000/mcp"]
       }
     }
   }
   ```

   **Important**: Use the **full absolute path** from `which mcp-proxy` - GUI apps like Claude Desktop don't inherit your terminal's PATH.

4. **Restart Claude Desktop completely**

5. **Verify connection**: Look for the MCP server indicator in Claude Desktop

### Example Queries

Once connected, try asking Claude:
- *"Find UK Supreme Court cases about employment law from 2020 onwards"*
- *"Search for legislation about data protection passed after 2015"*
- *"What cases cite the Data Protection Act 2018?"*

## 🏗️ Architecture

### Request Flow
```
Client Request → FastAPI Router → Search Service → Elasticsearch → Response
```

### Key Components
- **Routers** (`*/router.py`) - API endpoint definitions
- **Search Services** (`*/search.py`) - Query construction & execution  
- **Models** (`*/models.py`) - Request/response validation
- **Core** (`core/`) - Shared utilities & config

### Search Types
- **Text Search** - Traditional keyword matching
- **Semantic Search** - AI embeddings for conceptual matching (requires Azure OpenAI)

## ⚙️ Configuration

### Environment Variables
```bash
# Elasticsearch
ELASTIC_HOST=http://localhost:9200

# Azure OpenAI (for semantic search)
AZURE_OPENAI_API_KEY=your_key
AZURE_RESOURCE_NAME=your_resource
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Indices (customizable)
LEGISLATION_INDEX=lex-dev-legislation
CASELAW_INDEX=lex-dev-caselaw
```

### Index Naming
- Default pattern: `lex-dev-{type}`
- Types: `legislation`, `caselaw`, `explanatory-note`, `amendment`

## 🧪 Testing

### Run tests
```bash
uv run pytest tests/backend/
```

### Test specific endpoint
```bash
# Use test script
chmod +x test_all_endpoints.sh
./test_all_endpoints.sh
```

### Manual testing
Use the Swagger UI at http://localhost:8000/docs for interactive testing.

## 📈 Performance

| Operation | Typical Response Time | Notes |
|-----------|----------------------|--------|
| Text search | <100ms | Keyword matching |
| Semantic search | 200-500ms | Requires embedding generation |
| Full text retrieval | <200ms | Single document |
| Bulk operations | 1-5s | Depends on size |

## 🐛 Troubleshooting

### No search results
- Check indices have data: `curl http://localhost:9200/_cat/indices?v`
- Verify index names in environment variables

### Semantic search errors
- Check Azure OpenAI credentials in `.env`
- Update inference endpoint (see [Troubleshooting Guide](../../docs/troubleshooting.md))

### Slow responses
- Increase Elasticsearch heap size in `docker-compose.yaml`
- Reduce result `limit` in queries

## 📚 Further Reading

- [Ingestion Pipeline](../lex/README.md) - How data gets into the system
- [Data Models](../../docs/data-models.md) - Structure of legal documents
- [Troubleshooting](../../docs/troubleshooting.md) - Common issues & solutions