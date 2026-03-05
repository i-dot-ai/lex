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

## Amendments-led ingest finds no missing items

The amendments collection stores short-form IDs (e.g., `ukpga/2020/1`) while the legislation collection uses full URIs (e.g., `http://www.legislation.gov.uk/id/ukpga/2020/1`). The staleness check in `amendments_led.py` converts between these formats. If you see 0 missing/stale items when there should be some, check that `get_stale_or_missing_legislation_ids` is correctly prepending the base URI.

## Azure Container Apps Job env vars wiped after YAML update

Using `az containerapp job update --yaml` to change the job command can silently wipe environment variables and secrets if they aren't included in the YAML file. Always include all environment variables when updating a job via YAML. Check with:

```bash
az containerapp job show --name lex-ingest-job --resource-group rg-lex -o yaml | grep -A 50 "env:"
```

## Qdrant upload fails with payload too large

Qdrant has a 32MB payload limit per request. If uploading large batches, chunk the upsert into smaller batches (default: 100 points per chunk). The `_upload_batch` function in `orchestrator.py` handles this automatically with retry logic.
