# 📚 Lex Documentation Hub

Quick access to everything you need to work with Lex.

## 🚀 Start Here

- **New to Lex?** → [Quickstart Guide](../README.md#-quick-start-2-minutes--api-calls)
- **Setting up ingestion?** → [Ingestion Process](./ingestion-process.md)
- **Having issues?** → [Troubleshooting Guide](./troubleshooting.md)
- **Understanding data?** → [Data Models](./data-models.md)

## 📖 Core Documentation

### 📥 [Ingestion Process](./ingestion-process.md)
Understanding how documents are scraped, parsed, and indexed:
- Document types and sources
- Pipeline architecture
- Running ingestion commands
- Performance considerations

### 📊 [Logging System](./logging-system.md)
Structured logging for monitoring and debugging:
- Log architecture and flow
- Structured field reference
- Best practices
- Querying and analysis

### 💾 [Checkpointing System](./checkpointing-system.md)
Resilient processing with automatic resume:
- How checkpointing works
- Performance optimizations
- Managing checkpoints
- Troubleshooting

## Quick Links

### Getting Started
1. [Set up environment](../README.md#setup)
2. [Run sample ingestion](./ingestion-process.md#sample-data-quick-testing)
3. [Monitor progress](./logging-system.md#monitoring-and-alerting)
4. [Analyze results](../analysis/README.md)

### Common Tasks
- [Resume failed ingestion](./checkpointing-system.md#resuming-from-checkpoint)
- [Debug parsing errors](./logging-system.md#querying-logs)
- [Track processing speed](./ingestion-process.md#monitoring-progress)
- [Clear checkpoints](./checkpointing-system.md#clear-checkpoints)

### Architecture Overview
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Legislation    │────▶│   Scrapers      │────▶│   Parsers       │
│  .gov.uk        │     │   (Download)    │     │   (Extract)     │
│  (TNA API)      │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   Pipeline      │────▶│     Qdrant      │
                        │   (Process)     │     │  (Vector Store) │
                        │                 │     │   + Search      │
                        └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────┐
                                                │   FastAPI       │
                                                │   Backend       │
                                                │  (port 8000)    │
                                                └─────────────────┘

Data Flow:
- Ingestion: Scrapers → Parsers → Qdrant (direct with hybrid vectors)
- Search: Qdrant hybrid vector search (dense + sparse vectors)
- API: All search queries use Qdrant exclusively
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Code style and standards
- Testing requirements
- Documentation updates
- Pull request process