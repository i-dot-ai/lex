# Troubleshooting

Common issues and solutions when running Lex locally.

## Services won't start

```bash
docker system prune
docker compose down && docker compose up -d
```

## API returns no results

Check that collections are populated:

```bash
curl http://localhost:6333/collections | jq '.result.collections[] | {name, points_count}'
```

If collections are empty, run the data ingestion:

```bash
make ingest-all-sample
```

## Performance issues

Adjust batch size in `.env` for less memory usage:

```bash
PIPELINE_BATCH_SIZE=50
```

## MCP connection issues

If Claude Desktop or other MCP clients can't connect:

1. Verify the API is running: `curl http://localhost:8000/health`
2. Check the MCP endpoint: `curl http://localhost:8000/mcp`
3. Ensure your configuration file has the correct URL

## Embedding model issues

If you see errors about embeddings or Azure OpenAI:

1. Verify your `.env` has valid Azure OpenAI credentials
2. Check the embedding model deployment name matches your configuration
3. Ensure your Azure OpenAI endpoint is accessible

## Docker memory issues

If containers are being killed or running slowly:

```bash
# Check Docker resource limits
docker stats

# Increase Docker memory allocation in Docker Desktop settings
# Recommended: 8GB+ RAM for full dataset ingestion
```
